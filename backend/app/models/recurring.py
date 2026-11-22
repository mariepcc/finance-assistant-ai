import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, pg_enum
from app.models.enums import RecurringFrequency, TransactionType


def monthly_equivalent(frequency: RecurringFrequency, amount: Decimal) -> Decimal:
    if frequency == RecurringFrequency.YEARLY:
        return (amount / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amount


class RecurringRule(UUIDPk, Timestamps, Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="day_of_month_range"),
        CheckConstraint(
            "(frequency = 'yearly') = (month IS NOT NULL) "
            "AND (month IS NULL OR month BETWEEN 1 AND 12)",
            name="month_for_yearly",
        ),
        Index("ix_recurring_rules_user_due", "user_id", "next_due_on"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE")
    )
    type: Mapped[TransactionType] = mapped_column(pg_enum(TransactionType, "transaction_type"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="PLN")
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text)
    frequency: Mapped[RecurringFrequency] = mapped_column(
        pg_enum(RecurringFrequency, "recurring_frequency")
    )
    day_of_month: Mapped[int] = mapped_column(SmallInteger)
    month: Mapped[int | None] = mapped_column(SmallInteger)
    next_due_on: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    @property
    def monthly_amount(self) -> Decimal:
        return monthly_equivalent(self.frequency, self.amount)
