import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, pg_enum
from app.models.enums import BudgetPeriod


class Budget(UUIDPk, Timestamps, Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint(
            "user_id", "category_id", "period", name="uq_budgets_user_category_period"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    period: Mapped[BudgetPeriod] = mapped_column(
        pg_enum(BudgetPeriod, "budget_period"), server_default="monthly"
    )
