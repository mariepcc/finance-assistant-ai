from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConsentRequiredError, InvalidInputError, NotFoundError
from app.models import Budget, BudgetPeriod, Category, TransactionType
from app.repositories import analytics
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from app.schemas.budget import BudgetItem, BudgetsOut, BudgetSuggestion
from app.services import insights
from app.services.budget_status import budget_state, used_pct
from app.services.dashboard import month_end, parse_month, previous_month

AVERAGE_MONTHS = 3
ZERO = Decimal("0.00")


async def checked_main_category(
    session: AsyncSession, user_id: UUID, category_id: UUID
) -> Category:
    category = await categories_repo.get_for_user(session, user_id, category_id)
    if (
        category is None
        or category.archived_at is not None
        or category.kind != TransactionType.EXPENSE
    ):
        raise InvalidInputError("Nieznana kategoria wydatków")
    if category.parent_id is not None:
        parent = await categories_repo.get_for_user(session, user_id, category.parent_id)
        main = parent.name if parent else "główna"
        raise InvalidInputError(
            f"Budżet ustawiasz dla kategorii głównej („{main}”), "
            f"nie dla podkategorii „{category.name}”"
        )
    return category


async def upsert(
    session: AsyncSession, user_id: UUID, category_id: UUID, amount: Decimal
) -> Budget:
    await session.execute(
        insert(Budget)
        .values(
            user_id=user_id,
            category_id=category_id,
            amount=amount,
            period=BudgetPeriod.MONTHLY,
        )
        .on_conflict_do_update(
            constraint="uq_budgets_user_category_period",
            set_={"amount": amount, "updated_at": datetime.now(UTC)},
        )
    )
    budget = await analytics.budget_for_category(session, user_id, category_id)
    assert budget is not None
    await session.refresh(budget)
    return budget


async def save(session: AsyncSession, user_id: UUID, category_id: UUID, amount: Decimal) -> Budget:
    profile = await profiles_repo.get_or_create(session, user_id)
    if profile.gdpr_consent_at is None:
        raise ConsentRequiredError("Wymagana zgoda na przetwarzanie danych")
    await checked_main_category(session, user_id, category_id)
    return await upsert(session, user_id, category_id, amount)


async def remove(session: AsyncSession, user_id: UUID, category_id: UUID) -> None:
    result = await session.execute(
        delete(Budget).where(Budget.user_id == user_id, Budget.category_id == category_id)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise NotFoundError("Nie znaleziono budżetu")


async def averages(
    session: AsyncSession, user_id: UUID, before: date, category_ids: list[UUID]
) -> dict[UUID, Decimal | None]:
    first = await analytics.first_transaction_on(session, user_id)
    months = []
    start = before
    for _ in range(AVERAGE_MONTHS):
        start = previous_month(start)
        end = month_end(start)
        if first is not None and end >= first:
            months.append((start, end))
    result: dict[UUID, Decimal | None] = {}
    for category_id in category_ids:
        if not months:
            result[category_id] = None
            continue
        total = ZERO
        for start, end in months:
            totals = await analytics.totals(session, user_id, start, end, category_id)
            total += totals.expense
        result[category_id] = (total / len(months)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return result


async def overview(
    session: AsyncSession, user_id: UUID, month: str | None, today: date
) -> BudgetsOut:
    start = parse_month(month, today)
    end = month_end(start)
    is_current = start == today.replace(day=1)
    profile = await profiles_repo.get_or_create(session, user_id)
    usage = await analytics.budget_usage(session, user_id, start, end)
    categories = await categories_repo.list_for_user(session, user_id, TransactionType.EXPENSE)
    colors = {c.id: c.color for c in categories}
    avg = await averages(session, user_id, start, [u.budget.category_id for u in usage])
    items = []
    for u in usage:
        forecast = None
        if is_current:
            f = await insights.forecast_month_end(
                session, user_id, today, u.budget.category_id, u.budget.category_id
            )
            forecast = f.expense.typical
        items.append(
            BudgetItem(
                category_id=u.budget.category_id,
                category=u.category_name,
                color=colors.get(u.budget.category_id),
                limit=u.budget.amount,
                spent=u.spent,
                remaining=u.budget.amount - u.spent,
                used_pct=used_pct(u.spent, u.budget.amount),
                status=budget_state(u.spent, u.budget.amount),
                forecast_typical=forecast,
                average_monthly=avg.get(u.budget.category_id),
            )
        )
    return BudgetsOut(
        month=f"{start.year:04d}-{start.month:02d}",
        is_current=is_current,
        days_elapsed=today.day if is_current else end.day,
        days_in_month=end.day,
        currency=profile.default_currency,
        total_limit=sum((i.limit for i in items), ZERO),
        total_spent=sum((i.spent for i in items), ZERO),
        items=items,
    )


async def suggestions(session: AsyncSession, user_id: UUID, today: date) -> list[BudgetSuggestion]:
    categories = [
        c
        for c in await categories_repo.list_for_user(session, user_id, TransactionType.EXPENSE)
        if c.parent_id is None
    ]
    usage = await analytics.budget_usage(
        session, user_id, today.replace(day=1), month_end(today.replace(day=1))
    )
    budgeted = {u.budget.category_id for u in usage}
    avg = await averages(session, user_id, today.replace(day=1), [c.id for c in categories])
    return [
        BudgetSuggestion(
            category_id=c.id,
            category=c.name,
            color=c.color,
            average_monthly=avg.get(c.id),
            has_budget=c.id in budgeted,
        )
        for c in categories
    ]
