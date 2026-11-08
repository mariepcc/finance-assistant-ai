from datetime import date
from decimal import Decimal
from typing import Annotated

from app.models import TransactionType
from app.repositories import analytics
from pydantic import Field

from finance_tools.context import month_of, period, resolve_category, tool_context
from finance_tools.results import (
    BreakdownResult,
    CategoryComparison,
    CategoryShare,
    Change,
    CompareResult,
    Period,
    PeriodTotals,
    SimulationResult,
    SummaryResult,
    percent,
)

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
) -> BreakdownResult:
    p = period(date_from, date_to)
    async with tool_context() as ctx:
        rows = await analytics.breakdown_by_category(
            ctx.session, ctx.user_id, p.date_from, p.date_to, type
        )
        total = sum((r.total for r in rows), Decimal("0.00"))
        return BreakdownResult(
            period=p,
            type=type,
            currency=ctx.currency,
            total=total,
            categories=[
                CategoryShare(
                    category=r.name,
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
        str | None, Field(description="Opcjonalnie: porównaj tylko tę kategorię")
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
    category: Annotated[str, Field(description="Kategoria wydatku, np. Rozrywka")],
    purchase_date: Annotated[
        date | None, Field(description="Data zakupu; domyślnie dziś (liczy się jej miesiąc)")
    ] = None,
) -> SimulationResult:
    month = month_of(purchase_date or date.today())
    async with tool_context() as ctx:
        found = await resolve_category(ctx, category, TransactionType.EXPENSE)
        cat_totals = await analytics.totals(
            ctx.session, ctx.user_id, month.date_from, month.date_to, found.id
        )
        month_totals = await analytics.totals(
            ctx.session, ctx.user_id, month.date_from, month.date_to
        )
        budget = await analytics.budget_for_category(ctx.session, ctx.user_id, found.id)
        spent_after = cat_totals.expense + amount
        limit = budget.amount if budget else None
        return SimulationResult(
            currency=ctx.currency,
            month=month,
            category=found.name,
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
