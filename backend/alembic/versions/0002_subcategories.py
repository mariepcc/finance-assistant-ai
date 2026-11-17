"""Podkategorie: kategoria nadrzędna, opis, domyślne podkategorie dla istniejących kont.

Revision ID: 0002_subcategories
Revises: 0001_initial
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0002_subcategories"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_PARENTS = [
    (
        "Podróże",
        "airplane",
        "#0EA5E9",
        "wyjazdy poza miasto: przejazdy, noclegi, atrakcje",
    ),
]

PARENT_DESCRIPTIONS = {
    "Transport": "codzienne przemieszczanie się: dojazdy, komunikacja miejska, paliwo, taksówki",
}

SUBCATEGORIES: dict[str, list[tuple[str, str | None]]] = {
    "Jedzenie": [
        ("Spożywcze", "sklepy spożywcze, także zakupy spożywcze online"),
        ("Restauracje", "restauracje, obiady na mieście, bary"),
        ("Kawiarnie", "kawa i ciastko na mieście"),
        ("Zamówienia online", "dostawy jedzenia: Pyszne, Glovo, Uber Eats, Wolt"),
    ],
    "Transport": [
        ("Komunikacja miejska", "bilety i karty miejskie, regularne dojazdy pociągiem"),
        ("Paliwo", "paliwo, ładowanie auta"),
        ("Taksówki", "taksówki, Bolt, Uber"),
    ],
    "Podróże": [
        ("Przejazdy", "pociąg, autobus lub samolot na wyjazd do innego miasta"),
        ("Noclegi", "hotele, apartamenty, Airbnb"),
        ("Atrakcje", "bilety wstępu i wycieczki na wyjeździe"),
    ],
    "Mieszkanie": [
        ("Czynsz", "czynsz, najem"),
        ("Wyposażenie", "meble, sprzęt i dodatki do domu"),
        ("Remonty", "remonty, naprawy, materiały budowlane"),
    ],
    "Rachunki": [
        ("Prąd i gaz", None),
        ("Woda i ogrzewanie", None),
        ("Internet i telefon", None),
        ("Ubezpieczenia", "OC, ubezpieczenie mieszkania, na życie"),
        ("Subskrypcje", "iCloud, aplikacje, oprogramowanie; rozrywkowe to Streaming"),
    ],
    "Zdrowie": [
        ("Apteka", "leki, suplementy"),
        ("Lekarz", "wizyty, dentysta, badania"),
        ("Sport", "siłownia, zajęcia, sprzęt sportowy"),
    ],
    "Rozrywka": [
        ("Kino", None),
        ("Koncerty", None),
        ("Kultura", "teatr, muzea, wystawy, opera"),
        ("Książki", "książki, e-booki, audiobooki"),
        ("Gry", "gry, planszówki"),
        ("Streaming", "Spotify, Netflix i inne serwisy rozrywkowe"),
    ],
    "Zakupy": [
        ("Ubrania", "ubrania, obuwie, dodatki"),
        ("Elektronika", "telefony, komputery, słuchawki, akcesoria"),
        ("Drogeria", "kosmetyki i chemia domowa: Rossmann, Hebe"),
        ("Inne zakupy", "zakupy, które nie pasują do innych podkategorii"),
    ],
}


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column(
            "parent_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                "categories.id",
                ondelete="CASCADE",
                name="fk_categories_parent_id_categories",
            ),
        ),
    )
    op.add_column("categories", sa.Column("description", sa.Text()))
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    bind = op.get_bind()
    for name, icon, color, description in NEW_PARENTS:
        bind.execute(
            sa.text(
                "INSERT INTO categories "
                "(user_id, name, kind, icon, color, description, is_default) "
                "SELECT DISTINCT c.user_id, :name, 'expense'::transaction_type, "
                ":icon, :color, :description, true "
                "FROM categories c WHERE c.is_default "
                "ON CONFLICT DO NOTHING"
            ),
            {"name": name, "icon": icon, "color": color, "description": description},
        )
    for name, description in PARENT_DESCRIPTIONS.items():
        bind.execute(
            sa.text(
                "UPDATE categories SET description = :description "
                "WHERE is_default AND parent_id IS NULL AND name = :name AND description IS NULL"
            ),
            {"name": name, "description": description},
        )
    for parent, children in SUBCATEGORIES.items():
        for name, description in children:
            bind.execute(
                sa.text(
                    "INSERT INTO categories "
                    "(user_id, name, kind, color, description, is_default, parent_id) "
                    "SELECT p.user_id, :name, p.kind, p.color, :description, true, p.id "
                    "FROM categories p "
                    "WHERE p.is_default AND p.parent_id IS NULL AND p.name = :parent "
                    "AND p.archived_at IS NULL "
                    "ON CONFLICT DO NOTHING"
                ),
                {"name": name, "description": description, "parent": parent},
            )


def downgrade() -> None:
    op.execute("DELETE FROM categories WHERE parent_id IS NOT NULL")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_column("categories", "description")
    op.drop_column("categories", "parent_id")
