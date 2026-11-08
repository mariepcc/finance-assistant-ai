from datetime import date
from decimal import Decimal
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import TransactionType
from app.repositories import analytics
from app.repositories import transactions as tx_repo
from app.repositories.transactions import TransactionFilters
from tests.conftest import MakeUser


async def _add(client: AsyncClient, headers: dict[str, str], **body: str) -> None:
    r = await client.post("/transactions", json=body, headers=headers)
    assert r.status_code == 201, r.text


async def test_totals_and_breakdown_are_exact(
    client: AsyncClient, make_user: MakeUser, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    uid, headers, cats = await make_user()
    other_uid, other_headers, other_cats = await make_user()
    for amount, cat, day in [
        ("0.10", "Jedzenie", "2026-11-01"),
        ("0.20", "Jedzenie", "2026-11-02"),
        ("4.40", "Transport", "2026-11-03"),
        ("99.99", "Jedzenie", "2026-10-31"),
    ]:
        await _add(
            client, headers, type="expense", amount=amount, category_id=cats[cat], occurred_on=day
        )
    await _add(
        client,
        headers,
        type="income",
        amount="5000.00",
        category_id=cats["Wynagrodzenie"],
        occurred_on="2026-11-10",
    )
    await _add(
        client,
        other_headers,
        type="expense",
        amount="1000.00",
        category_id=other_cats["Jedzenie"],
        occurred_on="2026-11-05",
    )

    async with session_factory() as s:
        t = await analytics.totals(s, uid, date(2026, 11, 1), date(2026, 11, 30))
        assert (t.income, t.expense, t.balance, t.count) == (
            Decimal("5000.00"),
            Decimal("4.70"),
            Decimal("4995.30"),
            4,
        )
        food = await analytics.totals(
            s, uid, date(2026, 11, 1), date(2026, 11, 30), category_id=UUID(cats["Jedzenie"])
        )
        assert food.expense == Decimal("0.30")
        rows = await analytics.breakdown_by_category(
            s, uid, date(2026, 11, 1), date(2026, 11, 30), TransactionType.EXPENSE
        )
        assert [(r.name, r.total, r.count) for r in rows] == [
            ("Transport", Decimal("4.40"), 1),
            ("Jedzenie", Decimal("0.30"), 2),
        ]
        empty = await analytics.totals(s, uid, date(2026, 1, 1), date(2026, 1, 31))
        assert (empty.income, empty.expense, empty.count) == (Decimal("0.00"), Decimal("0.00"), 0)


async def test_amount_filters(
    client: AsyncClient, make_user: MakeUser, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    uid, headers, cats = await make_user()
    for amount in ("5.00", "50.00", "500.00"):
        await _add(
            client,
            headers,
            type="expense",
            amount=amount,
            category_id=cats["Zakupy"],
            occurred_on="2026-11-01",
        )
    async with session_factory() as s:
        items, _ = await tx_repo.list_for_user(
            s,
            uid,
            TransactionFilters(min_amount=Decimal("10"), max_amount=Decimal("500.00")),
            limit=10,
        )
    assert sorted(t.amount for t in items) == [Decimal("50.00"), Decimal("500.00")]
