from datetime import date
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import RecurringFrequency, TransactionType
from app.schemas.common import Money, ORMModel

Name = Field(min_length=1, max_length=100)
Day = Field(ge=1, le=31)
Month = Field(default=None, ge=1, le=12)


class Schedule(BaseModel):
    frequency: RecurringFrequency
    day_of_month: int = Day
    month: int | None = Month

    @model_validator(mode="after")
    def month_matches_frequency(self) -> Self:
        if self.frequency == RecurringFrequency.YEARLY and self.month is None:
            raise ValueError("Płatność roczna wymaga miesiąca")
        if self.frequency == RecurringFrequency.MONTHLY:
            self.month = None
        return self


class RecurringCreate(Schedule):
    type: TransactionType = TransactionType.EXPENSE
    amount: Money
    category_id: UUID
    name: str = Name


class RecurringUpdate(BaseModel):
    amount: Money | None = None
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    frequency: RecurringFrequency | None = None
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    month: int | None = Month
    active: bool | None = None


class RecurringOut(ORMModel):
    id: UUID
    type: TransactionType
    amount: Money
    currency: str
    category_id: UUID
    name: str
    frequency: RecurringFrequency
    day_of_month: int
    month: int | None
    next_due_on: date
    active: bool
    monthly_amount: Decimal


class RecurringList(BaseModel):
    items: list[RecurringOut]
    monthly_expense: Decimal
    monthly_income: Decimal
