from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import Money
from app.services.budget_status import BudgetState


class BudgetIn(BaseModel):
    amount: Money


class BudgetItem(BaseModel):
    category_id: UUID
    category: str
    color: str | None
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    used_pct: Decimal
    status: BudgetState
    forecast_typical: Decimal | None
    average_monthly: Decimal | None


class BudgetsOut(BaseModel):
    month: str
    is_current: bool
    days_elapsed: int
    days_in_month: int
    currency: str
    total_limit: Decimal
    total_spent: Decimal
    items: list[BudgetItem]


class BudgetSuggestion(BaseModel):
    category_id: UUID
    category: str
    color: str | None
    average_monthly: Decimal | None
    has_budget: bool
