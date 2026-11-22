from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal
from uuid import UUID

from app.models import RecurringFrequency, TransactionType
from pydantic import BaseModel, PlainSerializer

Amount = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]
Percent = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.1f}", return_type=str)]

CENT = Decimal("0.01")


def percent(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole == 0:
        return None
    return (part / whole * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class Period(BaseModel):
    date_from: date
    date_to: date


class SubcategoryInfo(BaseModel):
    name: str
    description: str | None = None


class CategoryInfo(BaseModel):
    name: str
    kind: TransactionType
    description: str | None = None
    subcategories: list[SubcategoryInfo] = []


class CategoriesResult(BaseModel):
    categories: list[CategoryInfo]


class TransactionItem(BaseModel):
    occurred_on: date
    type: TransactionType
    amount: Amount
    currency: str
    category: str
    subcategory: str | None
    note: str | None


class SearchResult(BaseModel):
    currency: str
    matched_count: int
    matched_income: Amount
    matched_expense: Amount
    returned_count: int
    truncated: bool
    transactions: list[TransactionItem]


class ProposedItem(BaseModel):
    type: TransactionType
    amount: Amount
    currency: str
    category: str
    subcategory: str | None
    occurred_on: date
    note: str | None


class TransactionProposalResult(BaseModel):
    proposal_id: UUID
    status: Literal["pending"]
    expires_at: datetime
    items: list[ProposedItem]
    requires_user_confirmation: bool = True


class BudgetProposalResult(BaseModel):
    proposal_id: UUID
    status: Literal["pending"]
    expires_at: datetime
    category: str
    currency: str
    amount: Amount
    previous_amount: Amount | None
    requires_user_confirmation: bool = True


class SummaryResult(BaseModel):
    period: Period
    currency: str
    income: Amount
    expense: Amount
    balance: Amount
    transaction_count: int


class CategoryShare(BaseModel):
    category: str
    amount: Amount
    share_pct: Percent | None
    transaction_count: int


class BreakdownResult(BaseModel):
    period: Period
    type: TransactionType
    parent_category: str | None = None
    currency: str
    total: Amount
    categories: list[CategoryShare]


class PeriodTotals(BaseModel):
    period: Period
    income: Amount
    expense: Amount
    balance: Amount


class Change(BaseModel):
    amount: Amount
    pct: Percent | None


class CategoryComparison(BaseModel):
    category: str
    expense_a: Amount
    expense_b: Amount
    change: Change


class CompareResult(BaseModel):
    currency: str
    category: str | None
    period_a: PeriodTotals
    period_b: PeriodTotals
    expense_change: Change
    income_change: Change
    by_category: list[CategoryComparison]


class SimulationResult(BaseModel):
    currency: str
    month: Period
    category: str
    subcategory: str | None
    purchase_amount: Amount
    category_spent_before: Amount
    category_spent_after: Amount
    budget_limit: Amount | None
    budget_remaining_before: Amount | None
    budget_remaining_after: Amount | None
    exceeds_budget: bool | None
    month_balance_before: Amount
    month_balance_after: Amount


BudgetState = Literal["ok", "warning", "exceeded"]


class BudgetLine(BaseModel):
    category: str
    limit: Amount
    spent: Amount
    remaining: Amount
    used_pct: Percent
    status: BudgetState


class BudgetStatusResult(BaseModel):
    month: Period
    currency: str
    total_limit: Amount
    total_spent: Amount
    budgets: list[BudgetLine]


class RecurringItem(BaseModel):
    name: str
    type: TransactionType
    amount: Amount
    currency: str
    category: str
    subcategory: str | None
    frequency: RecurringFrequency
    day_of_month: int
    month: int | None
    next_payment_on: date
    active: bool
    monthly_amount: Amount


class RecurringListResult(BaseModel):
    currency: str
    active_count: int
    paused_count: int
    monthly_expense_total: Amount
    monthly_income_total: Amount
    payments: list[RecurringItem]


class RecurringProposalResult(BaseModel):
    proposal_id: UUID
    status: Literal["pending"]
    expires_at: datetime
    name: str
    type: TransactionType
    amount: Amount
    currency: str
    category: str
    subcategory: str | None
    frequency: RecurringFrequency
    day_of_month: int
    month: int | None
    first_payment_on: date
    monthly_amount: Amount
    requires_user_confirmation: bool = True


Ratio = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.1f}", return_type=str)]


class ForecastRange(BaseModel):
    low: Amount
    typical: Amount
    high: Amount


class ForecastResult(BaseModel):
    currency: str
    month: Period
    category: str | None
    subcategory: str | None
    days_elapsed: int
    days_remaining: int
    spent_to_date: Amount
    planned_recurring_expense: Amount
    variable_spending_remaining: ForecastRange
    month_end_expense: ForecastRange
    current_pace_projection: Amount
    method: Literal["history_windows", "current_pace"]
    history_days: int
    income_to_date: Amount | None = None
    planned_recurring_income: Amount | None = None
    month_end_balance: ForecastRange | None = None
    budget_limit: Amount | None = None
    likely_exceeds_budget: bool | None = None


class AnomalyItem(BaseModel):
    occurred_on: date
    amount: Amount
    category: str
    subcategory: str | None
    note: str | None
    compared_with: str
    median_amount: Amount
    times_median: Ratio
    history_count: int


class CategoryAnomalyItem(BaseModel):
    category: str
    total: Amount
    expected: Amount
    median_month_total: Amount
    times_expected: Ratio
    months_compared: int


class AnomalyRules(BaseModel):
    transaction: str
    category: str


class AnomaliesResult(BaseModel):
    currency: str
    period: Period
    transactions: list[AnomalyItem]
    categories: list[CategoryAnomalyItem]
    partial_period: bool
    category_check_done: bool
    rules: AnomalyRules
