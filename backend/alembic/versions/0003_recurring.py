"""Stałe zlecenia: reguły płatności cyklicznych i powiązanie transakcji z regułą.

Revision ID: 0003_recurring
Revises: 0002_subcategories
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0003_recurring"
down_revision: str | None = "0002_subcategories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

transaction_type = pg.ENUM(name="transaction_type", create_type=False)
recurring_frequency = pg.ENUM("monthly", "yearly", name="recurring_frequency", create_type=False)


def upgrade() -> None:
    op.execute("ALTER TYPE transaction_source ADD VALUE IF NOT EXISTS 'recurring'")
    op.execute("ALTER TYPE proposal_kind ADD VALUE IF NOT EXISTS 'recurring'")
    recurring_frequency.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "recurring_rules",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="PLN", nullable=False),
        sa.Column(
            "category_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("frequency", recurring_frequency, nullable=False),
        sa.Column("day_of_month", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger()),
        sa.Column("next_due_on", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="ck_recurring_rules_amount_positive"),
        sa.CheckConstraint(
            "day_of_month BETWEEN 1 AND 31", name="ck_recurring_rules_day_of_month_range"
        ),
        sa.CheckConstraint(
            "(frequency = 'yearly') = (month IS NOT NULL) "
            "AND (month IS NULL OR month BETWEEN 1 AND 12)",
            name="ck_recurring_rules_month_for_yearly",
        ),
    )
    op.create_index("ix_recurring_rules_user_due", "recurring_rules", ["user_id", "next_due_on"])
    op.execute("ALTER TABLE recurring_rules ENABLE ROW LEVEL SECURITY")

    op.add_column(
        "transactions",
        sa.Column(
            "recurring_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                "recurring_rules.id",
                ondelete="SET NULL",
                name="fk_transactions_recurring_id_recurring_rules",
            ),
        ),
    )
    op.create_index(
        "uq_transactions_recurring_date",
        "transactions",
        ["recurring_id", "occurred_on"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_recurring_date", table_name="transactions")
    op.drop_column("transactions", "recurring_id")
    op.drop_table("recurring_rules")
    recurring_frequency.drop(op.get_bind(), checkfirst=True)
    op.execute("UPDATE transactions SET source = 'manual' WHERE source = 'recurring'")
