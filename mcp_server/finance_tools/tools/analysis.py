from datetime import date
from decimal import Decimal
from typing import Annotated

from app.models import TransactionType
from app.repositories import analytics
from app.services import insights
from pydantic import Field

from finance_tools.context import main_category, month_of, period, resolve_category, tool_context
from finance_tools.results import (
    AnomaliesResult,
    AnomalyItem,
    AnomalyRules,
    BreakdownResult,
    CategoryAnomalyItem,
    CategoryComparison,
    CategoryShare,
    Change,
    CompareResult,
    ForecastRange,
    ForecastResult,
    Period,
    PeriodTotals,
    SimulationResult,
    SummaryResult,
    percent,
)

OTHER_LABEL = "Pozostałe"

DateFrom = Annotated[date, Field(description="Początek okresu (RRRR-MM-DD)")]
DateTo = Annotated[date, Field(description="Koniec okresu włącznie (RRRR-MM-DD)")]


def _period_totals(p: Period, t: analytics.Totals) -> PeriodTotals:
    return PeriodTotals(period=p, income=t.income, expense=t.expense, balance=t.balance)


def _change(before: Decimal, after: Decimal) -> Change:
    return Change(amount=after - before, pct=percent(after - before, before))


async def get_summary(date_from: DateFrom, date_to: DateTo) -> SummaryResult:
    p = period(date_from, date_to)
    async with tool_context() as ctx:
        t = await analytics.totals(ctx.session, ctx.user_id, p.date_from, p.date_to)
        return SummaryResult(
            period=p,
            currency=ctx.currency,
            income=t.income,
            expense=t.expense,
            balance=t.balance,
            transaction_count=t.count,
        )


async def get_breakdown_by_category(
    date_from: DateFrom,
    date_to: DateTo,
    type: Annotated[
        TransactionType, Field(description="expense (domyślnie) albo income")
    ] = TransactionType.EXPENSE,
    category: Annotated[
        str | None,
        Field(
            description=(
                "Opcjonalnie kategoria główna, np. Jedzenie: rozbicie na jej podkategorie. "
                "Pozycja Pozostałe to wydatki bez podkategorii. "
                "Bez tego rozbicie na kategorie główne."
            )
        ),
    ] = None,
) -> BreakdownResult:
    p = period(date_from, date_to)
    async with tool_context() as ctx:
        parent = None
        if category is not None:
            parent = await main_category(ctx, await resolve_category(ctx, category, type))
        rows = await analytics.breakdown_by_category(
            ctx.session, ctx.user_id, p.date_from, p.date_to, type, parent.id if parent else None
        )
        total = sum((r.total for r in rows), Decimal("0.00"))
        return BreakdownResult(
            period=p,
            type=type,
            parent_category=parent.name if parent else None,
            currency=ctx.currency,
            total=total,
            categories=[
                CategoryShare(
                    category=(
                        OTHER_LABEL if parent is not None and r.category_id == parent.id else r.name
                    ),
                    amount=r.total,
                    share_pct=percent(r.total, total),
                    transaction_count=r.count,
                )
                for r in rows
            ],
        )


async def compare_periods(
    period_a_from: Annotated[date, Field(description="Początek okresu bazowego (wcześniejszego)")],
    period_a_to: Annotated[date, Field(description="Koniec okresu bazowego")],
    period_b_from: Annotated[date, Field(description="Początek okresu porównywanego")],
    period_b_to: Annotated[date, Field(description="Koniec okresu porównywanego")],
    category: Annotated[
        str | None,
        Field(description="Opcjonalnie: porównaj tylko tę kategorię lub podkategorię"),
    ] = None,
) -> CompareResult:
    pa = period(period_a_from, period_a_to)
    pb = period(period_b_from, period_b_to)
    async with tool_context() as ctx:
        category_id = None
        category_name = None
        if category is not None:
            found = await resolve_category(ctx, category)
            category_id, category_name = found.id, found.name
        ta = await analytics.totals(ctx.session, ctx.user_id, pa.date_from, pa.date_to, category_id)
        tb = await analytics.totals(ctx.session, ctx.user_id, pb.date_from, pb.date_to, category_id)
        by_category: list[CategoryComparison] = []
        if category_id is None:
            exp = TransactionType.EXPENSE
            ra = await analytics.breakdown_by_category(
                ctx.session, ctx.user_id, pa.date_from, pa.date_to, exp
            )
            rb = await analytics.breakdown_by_category(
                ctx.session, ctx.user_id, pb.date_from, pb.date_to, exp
            )
            a_map = {r.name: r.total for r in ra}
            b_map = {r.name: r.total for r in rb}
            zero = Decimal("0.00")
            names = sorted(
                set(a_map) | set(b_map),
                key=lambda n: abs(b_map.get(n, zero) - a_map.get(n, zero)),
                reverse=True,
            )
            by_category = [
                CategoryComparison(
                    category=n,
                    expense_a=a_map.get(n, zero),
                    expense_b=b_map.get(n, zero),
                    change=_change(a_map.get(n, zero), b_map.get(n, zero)),
                )
                for n in names
            ]
        return CompareResult(
            currency=ctx.currency,
            category=category_name,
            period_a=PeriodTotals(
                period=pa, income=ta.income, expense=ta.expense, balance=ta.balance
            ),
            period_b=PeriodTotals(
                period=pb, income=tb.income, expense=tb.expense, balance=tb.balance
            ),
            expense_change=_change(ta.expense, tb.expense),
            income_change=_change(ta.income, tb.income),
            by_category=by_category,
        )


async def simulate_purchase(
    amount: Annotated[
        Decimal, Field(gt=0, max_digits=12, decimal_places=2, description="Kwota zakupu")
    ],
    category: Annotated[
        str, Field(description="Kategoria lub podkategoria wydatku, np. Elektronika")
    ],
    purchase_date: Annotated[
        date | None, Field(description="Data zakupu; domyślnie dziś (liczy się jej miesiąc)")
    ] = None,
) -> SimulationResult:
    month = month_of(purchase_date or date.today())
    async with tool_context() as ctx:
        found = await resolve_category(ctx, category, TransactionType.EXPENSE)
        main = await main_category(ctx, found)
        cat_totals = await analytics.totals(
            ctx.session, ctx.user_id, month.date_from, month.date_to, main.id
        )
        month_totals = await analytics.totals(
            ctx.session, ctx.user_id, month.date_from, month.date_to
        )
        budget = await analytics.budget_for_category(ctx.session, ctx.user_id, main.id)
        spent_after = cat_totals.expense + amount
        limit = budget.amount if budget else None
        return SimulationResult(
            currency=ctx.currency,
            month=month,
            category=main.name,
            subcategory=found.name if found.id != main.id else None,
            purchase_amount=amount,
            category_spent_before=cat_totals.expense,
            category_spent_after=spent_after,
            budget_limit=limit,
            budget_remaining_before=limit - cat_totals.expense if limit is not None else None,
            budget_remaining_after=limit - spent_after if limit is not None else None,
            exceeds_budget=spent_after > limit if limit is not None else None,
            month_balance_before=month_totals.balance,
            month_balance_after=month_totals.balance - amount,
        )


def _range(r: insights.Range) -> ForecastRange:
    return ForecastRange(low=r.low, typical=r.typical, high=r.high)


async def forecast_month_end(
    category: Annotated[
        str | None,
        Field(
            description=(
                "Opcjonalnie kategoria lub podkategoria wydatków, np. Jedzenie. "
                "Bez tego prognoza wszystkich wydatków i salda."
            )
        ),
    ] = None,
) -> ForecastResult:
    today = date.today()
    async with tool_context() as ctx:
        found = main = None
        if category is not None:
            found = await resolve_category(ctx, category, TransactionType.EXPENSE)
            main = await main_category(ctx, found)
        f = await insights.forecast_month_end(
            ctx.session,
            ctx.user_id,
            today,
            found.id if found else None,
            main.id if main and found and main.id == found.id else None,
        )
        return ForecastResult(
            currency=ctx.currency,
            month=Period(date_from=f.month_start, date_to=f.month_end),
            category=main.name if main else None,
            subcategory=found.name if found and main and found.id != main.id else None,
            days_elapsed=f.days_elapsed,
            days_remaining=f.days_remaining,
            spent_to_date=f.spent_to_date,
            planned_recurring_expense=f.planned_recurring_expense,
            variable_spending_remaining=_range(f.variable),
            month_end_expense=_range(f.expense),
            current_pace_projection=f.pace_projection,
            method=f.method,
            history_days=f.history_days,
            income_to_date=f.income_to_date,
            planned_recurring_income=f.planned_recurring_income,
            month_end_balance=_range(f.balance) if f.balance else None,
            budget_limit=f.budget_limit,
            likely_exceeds_budget=f.likely_exceeds_budget,
        )


async def detect_anomalies(
    date_from: Annotated[
        date | None, Field(description="Początek okresu (RRRR-MM-DD); domyślnie 1. dzień miesiąca")
    ] = None,
    date_to: Annotated[
        date | None, Field(description="Koniec okresu (RRRR-MM-DD); domyślnie koniec miesiąca")
    ] = None,
) -> AnomaliesResult:
    today = date.today()
    month = month_of(today)
    p = period(date_from or month.date_from, date_to or month.date_to)
    async with tool_context() as ctx:
        found = await insights.detect_anomalies(
            ctx.session, ctx.user_id, p.date_from, p.date_to, today
        )
        return AnomaliesResult(
            currency=ctx.currency,
            period=p,
            transactions=[
                AnomalyItem(
                    occurred_on=a.occurred_on,
                    amount=a.amount,
                    category=a.category,
                    subcategory=a.subcategory,
                    note=a.note,
                    compared_with=a.compared_with,
                    median_amount=a.median,
                    times_median=a.ratio,
                    history_count=a.history_count,
                )
                for a in found.transactions
            ],
            categories=[
                CategoryAnomalyItem(
                    category=c.category,
                    total=c.total,
                    expected=c.expected,
                    median_month_total=c.median_month,
                    times_expected=c.ratio,
                    months_compared=c.months_compared,
                )
                for c in found.categories
            ],
            partial_period=found.partial_period,
            category_check_done=found.category_check,
            rules=AnomalyRules(
                transaction=(
                    "wydatek co najmniej 3 razy większy od mediany podkategorii z ostatnich "
                    "180 dni (kategorii głównej, gdy podkategoria ma mniej niż 5 wydatków; "
                    "patrz compared_with) i większy od niej o co najmniej 50 zł; stałe "
                    "płatności pominięte"
                ),
                category=(
                    "suma kategorii co najmniej 1,5 raza większa od mediany z 3 poprzednich "
                    "miesięcy (przeskalowanej dla niepełnego miesiąca) i większa o co najmniej "
                    "100 zł; stałe płatności pominięte"
                ),
            ),
        )
