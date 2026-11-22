"""Paleta kategorii przyjazna dla daltonistów: nowe kolory domyślnych kategorii wydatków.

Revision ID: 0004_category_palette
Revises: 0003_recurring
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_category_palette"
down_revision: str | None = "0003_recurring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PALETTE = {
    "Jedzenie": ("#F97316", "#EB6834"),
    "Transport": ("#3B82F6", "#2A78D6"),
    "Podróże": ("#0EA5E9", "#1BAF7A"),
    "Mieszkanie": ("#8B5CF6", "#6250D6"),
    "Rachunki": ("#64748B", "#EDA100"),
    "Zdrowie": ("#EF4444", "#E34948"),
    "Rozrywka": ("#EC4899", "#E87BA4"),
    "Zakupy": ("#14B8A6", "#008300"),
}

RECOLOR = sa.text(
    "UPDATE categories c SET color = :new "
    "WHERE c.color = :old AND c.is_default AND ("
    "(c.parent_id IS NULL AND c.name = :name) OR "
    "c.parent_id IN (SELECT p.id FROM categories p "
    "WHERE p.parent_id IS NULL AND p.is_default AND p.name = :name))"
)


def upgrade() -> None:
    bind = op.get_bind()
    for name, (old, new) in PALETTE.items():
        bind.execute(RECOLOR, {"name": name, "old": old, "new": new})


def downgrade() -> None:
    bind = op.get_bind()
    for name, (old, new) in PALETTE.items():
        bind.execute(RECOLOR, {"name": name, "old": new, "new": old})
