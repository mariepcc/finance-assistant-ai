from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ProposalKind, ProposalStatus, TransactionType
from app.schemas.common import Money, ORMModel
from app.schemas.transaction import TransactionOut


class ProposedTransaction(BaseModel):
    type: TransactionType
    amount: Money
    category: str = Field(min_length=1, max_length=100)
    occurred_on: date
    note: str | None = Field(default=None, max_length=500)


class TransactionProposalItem(BaseModel):
    type: TransactionType
    amount: Money
    currency: str
    category_id: UUID
    category: str
    occurred_on: date
    note: str | None


class TransactionProposalPayload(BaseModel):
    items: list[TransactionProposalItem]


class BudgetProposalPayload(BaseModel):
    category_id: UUID
    category: str
    amount: Money
    currency: str
    previous_amount: Decimal | None


class ProposalOut(ORMModel):
    id: UUID
    kind: ProposalKind
    status: ProposalStatus
    payload: dict[str, Any]
    expires_at: datetime


class BudgetOut(ORMModel):
    id: UUID
    category_id: UUID
    amount: Money


class ConfirmOut(BaseModel):
    proposal: ProposalOut
    transactions: list[TransactionOut] = []
    budget: BudgetOut | None = None
