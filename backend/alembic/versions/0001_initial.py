"""Model danych tygodnia 1: profile, kategorie, transakcje, budżety, propozycje.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["profiles", "categories", "proposals", "transactions", "budgets"]

transaction_type = pg.ENUM("expense", "income", name="transaction_type", create_type=False)
transaction_source = pg.ENUM("manual", "assistant", name="transaction_source", create_type=False)
budget_period = pg.ENUM("monthly", name="budget_period", create_type=False)
proposal_kind = pg.ENUM("transaction", "budget", name="proposal_kind", create_type=False)
proposal_status = pg.ENUM(
    "pending", "confirmed", "rejected", "expired", name="proposal_status", create_type=False
)
ENUMS = [transaction_type, transaction_source, budget_period, proposal_kind, proposal_status]


def _id() -> sa.Column[sa.Uuid]:
    return sa.Column(
        "id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def _user_id() -> sa.Column[sa.Uuid]:
    return sa.Column(
        "user_id",
        pg.UUID(as_uuid=True),
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "profiles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("default_currency", sa.CHAR(3), server_default="PLN", nullable=False),
        sa.Column("gdpr_consent_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )

    op.create_table(
        "categories",
        _id(),
        _user_id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", transaction_type, nullable=False),
        sa.Column("icon", sa.Text()),
        sa.Column("color", sa.Text()),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])
    op.create_index(
        "uq_categories_user_kind_name",
        "categories",
        ["user_id", "kind", sa.text("lower(name)")],
        unique=True,
    )

    op.create_table(
        "proposals",
        _id(),
        _user_id(),
        sa.Column("kind", proposal_kind, nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("status", proposal_status, server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_proposals_user_id", "proposals", ["user_id"])

    op.create_table(
        "transactions",
        _id(),
        _user_id(),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="PLN", nullable=False),
        sa.Column(
            "category_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("source", transaction_source, server_default="manual", nullable=False),
        sa.Column(
            "proposal_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("proposals.id", ondelete="SET NULL"),
        ),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
    )
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "occurred_on"])
    op.create_index(
        "ix_transactions_user_category_date",
        "transactions",
        ["user_id", "category_id", "occurred_on"],
    )

    op.create_table(
        "budgets",
        _id(),
        _user_id(),
        sa.Column(
            "category_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("period", budget_period, server_default="monthly", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_budgets_amount_positive"),
        sa.UniqueConstraint(
            "user_id", "category_id", "period", name="uq_budgets_user_category_period"
        ),
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
    bind = op.get_bind()
    for enum in reversed(ENUMS):
        enum.drop(bind, checkfirst=True)
