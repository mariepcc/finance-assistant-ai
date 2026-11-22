import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConsentRequiredError, InvalidInputError, NotFoundError
from app.models import (
    Category,
    RecurringFrequency,
    RecurringRule,
    Transaction,
    TransactionSource,
    TransactionType,
)
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from app.schemas.recurring import RecurringCreate, RecurringUpdate, Schedule

MAX_CATCH_UP = 400


def _clamped(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def due_on_or_after(
    frequency: RecurringFrequency, day_of_month: int, month: int | None, start: date
) -> date:
    if frequency == RecurringFrequency.YEARLY:
        assert month is not None
        candidate = _clamped(start.year, month, day_of_month)
        return candidate if candidate >= start else _clamped(start.year + 1, month, day_of_month)
    candidate = _clamped(start.year, start.month, day_of_month)
    if candidate >= start:
        return candidate
    year, next_month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return _clamped(year, next_month, day_of_month)


def following(rule: RecurringRule) -> date:
    return due_on_or_after(
        rule.frequency, rule.day_of_month, rule.month, rule.next_due_on + timedelta(days=1)
    )


def first_due(schedule: Schedule, today: date) -> date:
    return due_on_or_after(schedule.frequency, schedule.day_of_month, schedule.month, today)


@dataclass(frozen=True, slots=True)
class Totals:
    expense: Decimal
    income: Decimal


def monthly_totals(rules: Sequence[RecurringRule]) -> Totals:
    expense = Decimal("0.00")
    income = Decimal("0.00")
    for rule in rules:
        if not rule.active:
            continue
        value = rule.monthly_amount
        if rule.type == TransactionType.EXPENSE:
            expense += value
        else:
            income += value
    return Totals(expense=expense, income=income)


async def materialize_due(session: AsyncSession, user_id: UUID, today: date) -> int:
    rules = (
        await session.scalars(
            select(RecurringRule)
            .where(
                RecurringRule.user_id == user_id,
                RecurringRule.active.is_(True),
                RecurringRule.next_due_on <= today,
            )
            .with_for_update()
        )
    ).all()
    booked = 0
    for rule in rules:
        steps = 0
        while rule.next_due_on <= today and steps < MAX_CATCH_UP:
            result = await session.execute(
                insert(Transaction)
                .values(
                    user_id=user_id,
                    type=rule.type,
                    amount=rule.amount,
                    currency=rule.currency,
                    category_id=rule.category_id,
                    occurred_on=rule.next_due_on,
                    note=rule.name,
                    source=TransactionSource.RECURRING,
                    recurring_id=rule.id,
                )
                .on_conflict_do_nothing(index_elements=["recurring_id", "occurred_on"])
                .returning(Transaction.id)
            )
            booked += len(result.all())
            rule.next_due_on = following(rule)
            steps += 1
    if rules:
        await session.flush()
    return booked


async def list_for_user(session: AsyncSession, user_id: UUID) -> Sequence[RecurringRule]:
    rows = await session.scalars(
        select(RecurringRule)
        .where(RecurringRule.user_id == user_id)
        .order_by(RecurringRule.active.desc(), RecurringRule.next_due_on, RecurringRule.name)
    )
    return rows.all()


async def get(session: AsyncSession, user_id: UUID, rule_id: UUID) -> RecurringRule:
    rule = await session.scalar(
        select(RecurringRule).where(RecurringRule.id == rule_id, RecurringRule.user_id == user_id)
    )
    if rule is None:
        raise NotFoundError("Nie znaleziono stałej płatności")
    return rule


async def checked_category(
    session: AsyncSession, user_id: UUID, category_id: UUID, kind: TransactionType
) -> Category:
    category = await categories_repo.get_for_user(session, user_id, category_id)
    if category is None or category.archived_at is not None or category.kind != kind:
        raise InvalidInputError("Wybrana kategoria nie pasuje do typu płatności")
    return category


async def create(
    session: AsyncSession, user_id: UUID, data: RecurringCreate, today: date
) -> RecurringRule:
    profile = await profiles_repo.get_or_create(session, user_id)
    if profile.gdpr_consent_at is None:
        raise ConsentRequiredError("Wymagana zgoda na przetwarzanie danych")
    await checked_category(session, user_id, data.category_id, data.type)
    rule = RecurringRule(
        user_id=user_id,
        type=data.type,
        amount=data.amount,
        currency=profile.default_currency,
        category_id=data.category_id,
        name=data.name.strip(),
        frequency=data.frequency,
        day_of_month=data.day_of_month,
        month=data.month,
        next_due_on=first_due(data, today),
        active=True,
    )
    session.add(rule)
    await session.flush()
    await materialize_due(session, user_id, today)
    await session.refresh(rule)
    return rule


async def update(
    session: AsyncSession, user_id: UUID, rule_id: UUID, data: RecurringUpdate, today: date
) -> RecurringRule:
    rule = await get(session, user_id, rule_id)
    changes = data.model_dump(exclude_unset=True)
    for field in ("amount", "category_id", "name", "frequency", "day_of_month", "active"):
        if field in changes and changes[field] is None:
            raise InvalidInputError(f"Pole {field} nie może być puste")
    if "category_id" in changes:
        await checked_category(session, user_id, changes["category_id"], rule.type)
        rule.category_id = changes["category_id"]
    if "amount" in changes:
        rule.amount = changes["amount"]
    if "name" in changes:
        rule.name = changes["name"].strip()
    schedule_keys = {"frequency", "day_of_month", "month"}
    resumed = changes.get("active") is True and not rule.active
    if schedule_keys & changes.keys():
        try:
            schedule = Schedule(
                frequency=changes.get("frequency", rule.frequency),
                day_of_month=changes.get("day_of_month", rule.day_of_month),
                month=changes.get("month", rule.month),
            )
        except ValidationError as exc:
            raise InvalidInputError("Płatność roczna wymaga miesiąca") from exc
        rule.frequency = schedule.frequency
        rule.day_of_month = schedule.day_of_month
        rule.month = schedule.month
    if "active" in changes:
        rule.active = changes["active"]
    if resumed or schedule_keys & changes.keys():
        rule.next_due_on = due_on_or_after(rule.frequency, rule.day_of_month, rule.month, today)
    await session.flush()
    await materialize_due(session, user_id, today)
    await session.refresh(rule)
    return rule


async def delete(session: AsyncSession, user_id: UUID, rule_id: UUID) -> None:
    rule = await get(session, user_id, rule_id)
    await session.delete(rule)
    await session.flush()
