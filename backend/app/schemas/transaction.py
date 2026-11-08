from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TransactionSource, TransactionType
from app.schemas.common import Currency, Money, ORMModel


class TransactionCreate(BaseModel):
    type: TransactionType
    amount: Money
    category_id: UUID
    occurred_on: date
    currency: Currency | None = None
    note: str | None = Field(default=None, max_length=500)


class TransactionUpdate(BaseModel):
    type: TransactionType | None = None
    amount: Money | None = None
    category_id: UUID | None = None
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class TransactionOut(ORMModel):
    id: UUID
    type: TransactionType
    amount: Money
    currency: str
    category_id: UUID
    occurred_on: date
    note: str | None
    source: TransactionSource
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    next_cursor: str | None
