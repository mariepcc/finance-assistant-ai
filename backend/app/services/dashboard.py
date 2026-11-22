import calendar
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import InvalidInputError
from app.models import RecurringRule
from app.repositories import analytics
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from app.schemas.dashboard import (
    BudgetLine,
    CategoryShare,
    Dashboard,
    ForecastRange,
    SubcategoryShare,
    UpcomingPayment,
)
from app.services import insights
from app.services.budget_status import budget_state, used_pct

ZERO = Decimal("0.00")
UPCOMING_DAYS = 14
UPCOMING_LIMIT = 5
OTHER_LABEL = "Pozostałe"


def parse_month(value: str | None, today: date) -> date:
    if value is None:
        return today.replace(day=1)
    try:
        year, month = (int(part) for part in value.split("-"))
        start = date(year, month, 1)
    except ValueError as exc:
        raise InvalidInputError("Miesiąc w formacie RRRR-MM, np. 2026-11") from exc
    if start > today:
        raise InvalidInputError("Nie można pokazać przyszłego miesiąca")
    return start


def month_end(start: date) -> date:
    return start.replace(day=calendar.monthrange(start.year, start.month)[1])


def previous_month(start: date) -> date:
    return (start - timedelta(days=1)).replace(day=1)


def share(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return Decimal("0.0")
    return (part / whole * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def cumulative(rows: Sequence[analytics.ExpenseRow], start: date, days: int) -> list[Decimal]:
    per_day = [ZERO] * days
    for row in rows:
        index = (row.occurred_on - start).days
        if 0 <= index < days:
            per_day[index] += row.amount
    result = []
    running = ZERO
    for value in per_day:
        running += value
        result.append(running)
    return result


def category_shares(
    rows: Sequence[analytics.ExpenseRow], colors: dict[UUID, str | None]
) -> list[CategoryShare]:
    total = sum((r.amount for r in rows), ZERO)
    main_total: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    main_count: dict[UUID, int] = defaultdict(int)
    main_name: dict[UUID, str] = {}
    leaves: dict[UUID, dict[UUID, tuple[str, Decimal]]] = defaultdict(dict)
    for row in rows:
        main_total[row.main_id] += row.amount
        main_count[row.main_id] += 1
        main_name[row.main_id] = row.main
        name, amount = leaves[row.main_id].get(row.category_id, (row.category, ZERO))
        leaves[row.main_id][row.category_id] = (name, amount + row.amount)
    result = []
    for main_id, amount in main_total.items():
        subs = []
        for leaf_id, (name, leaf_amount) in leaves[main_id].items():
            is_main = leaf_id == main_id
            subs.append(
                SubcategoryShare(
                    category_id=None if is_main else leaf_id,
                    name=OTHER_LABEL if is_main else name,
                    amount=leaf_amount,
                    share_pct=share(leaf_amount, amount),
                )
            )
        has_children = any(s.category_id is not None for s in subs)
        subs.sort(key=lambda s: (s.category_id is None, -s.amount, s.name))
        result.append(
            CategoryShare(
                category_id=main_id,
                name=main_name[main_id],
                color=colors.get(main_id),
                amount=amount,
                share_pct=share(amount, total),
                transaction_count=main_count[main_id],
                subcategories=subs if has_children else [],
            )
        )
    result.sort(key=lambda c: (-c.amount, c.name))
    return result


async def build(session: AsyncSession, user_id: UUID, month: str | None, today: date) -> Dashboard:
    start = parse_month(month, today)
    end = month_end(start)
    is_current = start == today.replace(day=1)
    days_in_month = end.day
    days_elapsed = today.day if is_current else days_in_month
    prev_start = previous_month(start)
    prev_end = month_end(prev_start)
    same_point = prev_start + timedelta(days=min(days_elapsed, prev_end.day) - 1)

    profile = await profiles_repo.get_or_create(session, user_id)
    totals = await analytics.totals(session, user_id, start, end)
    rows = await analytics.expense_rows(session, user_id, start, end)
    prev_rows = await analytics.expense_rows(session, user_id, prev_start, prev_end)
    categories = await categories_repo.list_for_user(session, user_id)
    colors = {c.id: c.color for c in categories}

    prev_same = sum((r.amount for r in prev_rows if r.occurred_on <= same_point), ZERO)
    prev_total = sum((r.amount for r in prev_rows), ZERO)
    change = (
        ((totals.expense - prev_same) / prev_same * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        if prev_same > 0
        else None
    )

    budgets = [
        BudgetLine(
            category_id=u.budget.category_id,
            category=u.category_name,
            color=colors.get(u.budget.category_id),
            limit=u.budget.amount,
            spent=u.spent,
            remaining=u.budget.amount - u.spent,
            used_pct=used_pct(u.spent, u.budget.amount),
            status=budget_state(u.spent, u.budget.amount),
        )
        for u in await analytics.budget_usage(session, user_id, start, end)
    ]

    upcoming: list[UpcomingPayment] = []
    forecast = None
    if is_current:
        rules = await session.scalars(
            select(RecurringRule)
            .where(
                RecurringRule.user_id == user_id,
                RecurringRule.active.is_(True),
                RecurringRule.next_due_on > today,
                RecurringRule.next_due_on <= today + timedelta(days=UPCOMING_DAYS),
            )
            .order_by(RecurringRule.next_due_on, RecurringRule.name)
            .limit(UPCOMING_LIMIT)
        )
        upcoming = [
            UpcomingPayment(
                id=r.id,
                name=r.name,
                type=r.type,
                amount=r.amount,
                currency=r.currency,
                due_on=r.next_due_on,
            )
            for r in rules.all()
        ]
        if rows or prev_rows:
            f = await insights.forecast_month_end(session, user_id, today)
            forecast = ForecastRange(
                low=f.expense.low, typical=f.expense.typical, high=f.expense.high
            )

    return Dashboard(
        month=f"{start.year:04d}-{start.month:02d}",
        date_from=start,
        date_to=end,
        is_current=is_current,
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
        currency=profile.default_currency,
        income=totals.income,
        expense=totals.expense,
        balance=totals.balance,
        transaction_count=totals.count,
        previous_month=f"{prev_start.year:04d}-{prev_start.month:02d}",
        previous_expense_same_point=prev_same,
        previous_expense_total=prev_total,
        expense_change_pct=change,
        daily=cumulative(rows, start, days_elapsed),
        previous_daily=cumulative(prev_rows, prev_start, prev_end.day),
        categories=category_shares(rows, colors),
        budgets=budgets,
        upcoming=upcoming,
        forecast=forecast,
    )
