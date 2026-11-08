from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Literal
from uuid import UUID

from app.models import TransactionType
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


class CategoryInfo(BaseModel):
    name: str
    kind: TransactionType


class CategoriesResult(BaseModel):
    categories: list[CategoryInfo]


class TransactionItem(BaseModel):
    occurred_on: date
    type: TransactionType
    amount: Amount
    currency: str
    category: str
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
