from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TransactionType
from app.services.budget_status import BudgetState


class SubcategoryShare(BaseModel):
    category_id: UUID | None
    name: str
    amount: Decimal
    share_pct: Decimal


class CategoryShare(BaseModel):
    category_id: UUID
    name: str
    color: str | None
    amount: Decimal
    share_pct: Decimal
    transaction_count: int
    subcategories: list[SubcategoryShare]


class BudgetLine(BaseModel):
    category_id: UUID
    category: str
    color: str | None
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    used_pct: Decimal
    status: BudgetState


class UpcomingPayment(BaseModel):
    id: UUID
    name: str
    type: TransactionType
    amount: Decimal
    currency: str
    due_on: date


class ForecastRange(BaseModel):
    low: Decimal
    typical: Decimal
    high: Decimal


class Dashboard(BaseModel):
    month: str
    date_from: date
    date_to: date
    is_current: bool
    days_elapsed: int
    days_in_month: int
    currency: str
    income: Decimal
    expense: Decimal
    balance: Decimal
    transaction_count: int
    previous_month: str
    previous_expense_same_point: Decimal
    previous_expense_total: Decimal
    expense_change_pct: Decimal | None
    daily: list[Decimal]
    previous_daily: list[Decimal]
    categories: list[CategoryShare]
    budgets: list[BudgetLine]
    upcoming: list[UpcomingPayment]
    forecast: ForecastRange | None
