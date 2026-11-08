import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CHAR, CheckConstraint, Date, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, pg_enum
from app.models.enums import TransactionSource, TransactionType


class Transaction(UUIDPk, Timestamps, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_transactions_user_date", "user_id", "occurred_on"),
        Index("ix_transactions_user_category_date", "user_id", "category_id", "occurred_on"),
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
    occurred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[TransactionSource] = mapped_column(
        pg_enum(TransactionSource, "transaction_source"), server_default="manual"
    )
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("proposals.id", ondelete="SET NULL")
    )
