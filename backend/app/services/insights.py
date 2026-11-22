import calendar
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RecurringRule, TransactionType
from app.repositories import analytics
from app.repositories import categories as categories_repo

CENT = Decimal("0.01")
TENTH = Decimal("0.1")
ZERO = Decimal("0.00")

FORECAST_HISTORY_DAYS = 90
MIN_HISTORY_DAYS = 28
PACE_SPREAD = Decimal("0.25")

ANOMALY_HISTORY_DAYS = 180
MIN_HISTORY_COUNT = 5
TX_RATIO = Decimal("3")
TX_MIN_DIFF = Decimal("50.00")
CATEGORY_RATIO = Decimal("1.5")
CATEGORY_MIN_DIFF = Decimal("100.00")
CATEGORY_MONTHS = 3

Method = Literal["history_windows", "current_pace"]


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def percentile(values: Sequence[Decimal], q: Decimal) -> Decimal:
    if not values:
        return ZERO
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return money(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def median(values: Sequence[Decimal]) -> Decimal:
    return percentile(values, Decimal("0.5"))


def window_sums(
    daily: Mapping[date, Decimal], start: date, end: date, length: int
) -> list[Decimal]:
    days = (end - start).days + 1
    if length <= 0 or days < length:
        return []
    amounts = [daily.get(start + timedelta(days=i), ZERO) for i in range(days)]
    current = sum(amounts[:length], ZERO)
    sums = [current]
    for i in range(length, days):
        current += amounts[i] - amounts[i - length]
        sums.append(current)
    return sums


@dataclass(frozen=True, slots=True)
class Range:
    low: Decimal
    typical: Decimal
    high: Decimal

    def plus(self, value: Decimal) -> "Range":
        return Range(self.low + value, self.typical + value, self.high + value)


def variable_range(
    windows: Sequence[Decimal], pace_projection: Decimal, use_history: bool
) -> tuple[Range, Method]:
    if use_history and windows:
        return (
            Range(
                percentile(windows, Decimal("0.1")),
                percentile(windows, Decimal("0.5")),
                percentile(windows, Decimal("0.9")),
            ),
            "history_windows",
        )
    return (
        Range(
            money(pace_projection * (1 - PACE_SPREAD)),
            pace_projection,
            money(pace_projection * (1 + PACE_SPREAD)),
        ),
        "current_pace",
    )


@dataclass(frozen=True, slots=True)
class Forecast:
    month_start: date
    month_end: date
    days_elapsed: int
    days_remaining: int
    spent_to_date: Decimal
    planned_recurring_expense: Decimal
    variable: Range
    expense: Range
    pace_projection: Decimal
    method: Method
    history_days: int
    income_to_date: Decimal | None = None
    planned_recurring_income: Decimal | None = None
    balance: Range | None = None
    budget_limit: Decimal | None = None
    likely_exceeds_budget: bool | None = None


def _daily(rows: Sequence[analytics.ExpenseRow]) -> dict[date, Decimal]:
    daily: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        if not row.recurring:
            daily[row.occurred_on] += row.amount
    return daily


async def _planned(
    session: AsyncSession,
    user_id: UUID,
    after: date,
    until: date,
    category_ids: list[UUID] | None,
) -> tuple[Decimal, Decimal]:
    stmt = select(RecurringRule).where(
        RecurringRule.user_id == user_id,
        RecurringRule.active.is_(True),
        RecurringRule.next_due_on > after,
        RecurringRule.next_due_on <= until,
    )
    if category_ids is not None:
        stmt = stmt.where(RecurringRule.category_id.in_(category_ids))
    expense = income = ZERO
    for rule in (await session.scalars(stmt)).all():
        if rule.type == TransactionType.EXPENSE:
            expense += rule.amount
        else:
            income += rule.amount
    return expense, income


async def forecast_month_end(
    session: AsyncSession,
    user_id: UUID,
    today: date,
    category_id: UUID | None = None,
    budget_category_id: UUID | None = None,
) -> Forecast:
    month_start = today.replace(day=1)
    month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    days_elapsed = today.day
    days_remaining = (month_end - today).days

    month_rows = await analytics.expense_rows(session, user_id, month_start, today, category_id)
    spent_to_date = sum((r.amount for r in month_rows), ZERO)
    variable_to_date = sum((r.amount for r in month_rows if not r.recurring), ZERO)
    pace_projection = money(variable_to_date / days_elapsed * days_remaining)

    first = await analytics.first_transaction_on(session, user_id)
    history_end = month_start - timedelta(days=1)
    history_start = month_start - timedelta(days=FORECAST_HISTORY_DAYS)
    if first is not None and first > history_start:
        history_start = first
    history_days = max((history_end - history_start).days + 1, 0)
    windows: list[Decimal] = []
    if history_days > 0 and days_remaining > 0:
        history_rows = await analytics.expense_rows(
            session, user_id, history_start, history_end, category_id
        )
        windows = window_sums(_daily(history_rows), history_start, history_end, days_remaining)
    variable, method = variable_range(
        windows, pace_projection, history_days >= MIN_HISTORY_DAYS and days_remaining > 0
    )

    scope = (
        await categories_repo.scope_ids(session, user_id, category_id)
        if category_id is not None
        else None
    )
    planned_expense, planned_income = await _planned(session, user_id, today, month_end, scope)
    expense = variable.plus(spent_to_date + planned_expense)

    result = Forecast(
        month_start=month_start,
        month_end=month_end,
        days_elapsed=days_elapsed,
        days_remaining=days_remaining,
        spent_to_date=spent_to_date,
        planned_recurring_expense=planned_expense,
        variable=variable,
        expense=expense,
        pace_projection=pace_projection,
        method=method,
        history_days=history_days,
    )
    if category_id is None:
        month_totals = await analytics.totals(session, user_id, month_start, today)
        income = month_totals.income + planned_income
        balance = Range(income - expense.high, income - expense.typical, income - expense.low)
        return replace(
            result,
            income_to_date=month_totals.income,
            planned_recurring_income=planned_income,
            balance=balance,
        )
    if budget_category_id is not None:
        budget = await analytics.budget_for_category(session, user_id, budget_category_id)
        if budget is not None:
            return replace(
                result,
                budget_limit=budget.amount,
                likely_exceeds_budget=expense.typical > budget.amount,
            )
    return result


@dataclass(frozen=True, slots=True)
class TransactionAnomaly:
    occurred_on: date
    amount: Decimal
    category: str
    subcategory: str | None
    note: str | None
    compared_with: str
    median: Decimal
    ratio: Decimal
    history_count: int


@dataclass(frozen=True, slots=True)
class CategoryAnomaly:
    category: str
    total: Decimal
    expected: Decimal
    median_month: Decimal
    ratio: Decimal
    months_compared: int


@dataclass
class Anomalies:
    transactions: list[TransactionAnomaly] = field(default_factory=list)
    categories: list[CategoryAnomaly] = field(default_factory=list)
    partial_period: bool = False
    category_check: bool = True


def ratio(value: Decimal, base: Decimal) -> Decimal:
    return (value / base).quantize(TENTH, rounding=ROUND_HALF_UP)


def transaction_anomalies(
    period_rows: Sequence[analytics.ExpenseRow], history_rows: Sequence[analytics.ExpenseRow]
) -> list[TransactionAnomaly]:
    by_leaf: dict[UUID, list[Decimal]] = defaultdict(list)
    by_main: dict[UUID, list[Decimal]] = defaultdict(list)
    for row in history_rows:
        if row.recurring:
            continue
        by_leaf[row.category_id].append(row.amount)
        by_main[row.main_id].append(row.amount)
    found = []
    for row in period_rows:
        if row.recurring:
            continue
        if len(by_leaf[row.category_id]) >= MIN_HISTORY_COUNT:
            history, compared_with = by_leaf[row.category_id], row.category
        elif len(by_main[row.main_id]) >= MIN_HISTORY_COUNT:
            history, compared_with = by_main[row.main_id], row.main
        else:
            continue
        mid = median(history)
        if mid <= 0:
            continue
        if row.amount >= mid * TX_RATIO and row.amount - mid >= TX_MIN_DIFF:
            found.append(
                TransactionAnomaly(
                    occurred_on=row.occurred_on,
                    amount=row.amount,
                    category=row.main,
                    subcategory=row.category if row.category_id != row.main_id else None,
                    note=row.note,
                    compared_with=compared_with,
                    median=mid,
                    ratio=ratio(row.amount, mid),
                    history_count=len(history),
                )
            )
    return sorted(found, key=lambda a: a.ratio, reverse=True)


def months_before(day: date, count: int) -> list[tuple[date, date]]:
    result = []
    year, month = day.year, day.month
    for _ in range(count):
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        last = calendar.monthrange(year, month)[1]
        result.append((date(year, month, 1), date(year, month, last)))
    return result


def category_anomalies(
    period_totals: Mapping[str, Decimal],
    monthly_history: Sequence[Mapping[str, Decimal]],
    factor: Decimal,
) -> list[CategoryAnomaly]:
    found = []
    for name, total in period_totals.items():
        mid = median([month.get(name, ZERO) for month in monthly_history])
        expected = money(mid * factor)
        if expected <= 0:
            continue
        if total >= expected * CATEGORY_RATIO and total - expected >= CATEGORY_MIN_DIFF:
            found.append(
                CategoryAnomaly(
                    category=name,
                    total=total,
                    expected=expected,
                    median_month=mid,
                    ratio=ratio(total, expected),
                    months_compared=len(monthly_history),
                )
            )
    return sorted(found, key=lambda a: a.ratio, reverse=True)


def _main_totals(rows: Sequence[analytics.ExpenseRow]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        if not row.recurring:
            totals[row.main] += row.amount
    return dict(totals)


async def detect_anomalies(
    session: AsyncSession, user_id: UUID, date_from: date, date_to: date, today: date
) -> Anomalies:
    period_rows = await analytics.expense_rows(session, user_id, date_from, date_to)
    history_rows = await analytics.expense_rows(
        session,
        user_id,
        date_from - timedelta(days=ANOMALY_HISTORY_DAYS),
        date_from - timedelta(days=1),
    )
    result = Anomalies(transactions=transaction_anomalies(period_rows, history_rows))

    if (date_from.year, date_from.month) != (date_to.year, date_to.month):
        result.category_check = False
        return result
    first = await analytics.first_transaction_on(session, user_id)
    months = [
        (start, end)
        for start, end in months_before(date_from, CATEGORY_MONTHS)
        if first is not None and first <= start
    ]
    if len(months) < 2:
        result.category_check = False
        return result
    history = [
        _main_totals(await analytics.expense_rows(session, user_id, start, end))
        for start, end in months
    ]
    days_in_month = calendar.monthrange(date_from.year, date_from.month)[1]
    covered = (min(date_to, today) - date_from).days + 1
    factor = Decimal(max(covered, 0)) / Decimal(days_in_month)
    result.partial_period = factor < 1
    result.categories = category_anomalies(_main_totals(period_rows), history, factor)
    return result
