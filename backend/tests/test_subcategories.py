from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import InvalidInputError
from app.models import Budget, TransactionType
from app.repositories import analytics
from app.schemas.proposal import ProposedTransaction
from app.services import proposals as svc
from tests.conftest import MakeUser

Factory = async_sessionmaker[AsyncSession]
OCT = (date(2026, 10, 1), date(2026, 10, 31))


async def add_tx(
    client: AsyncClient, headers: dict[str, str], category_id: str, amount: str, day: str
) -> None:
    r = await client.post(
        "/transactions",
        json={"type": "expense", "amount": amount, "category_id": category_id, "occurred_on": day},
        headers=headers,
    )
    assert r.status_code == 201, r.text


async def food_month(
    client: AsyncClient, make_user: MakeUser
) -> tuple[UUID, dict[str, str], dict[str, str]]:
    uid, headers, cats = await make_user()
    await add_tx(client, headers, cats["Restauracje"], "45.00", "2026-10-03")
    await add_tx(client, headers, cats["Kawiarnie"], "14.00", "2026-10-04")
    await add_tx(client, headers, cats["Jedzenie"], "20.00", "2026-10-05")
    await add_tx(client, headers, cats["Paliwo"], "200.00", "2026-10-06")
    return uid, headers, cats


async def test_parent_totals_and_filters_include_subcategories(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await food_month(client, make_user)
    async with session_factory() as s:
        food = await analytics.totals(s, uid, *OCT, UUID(cats["Jedzenie"]))
        cafe = await analytics.totals(s, uid, *OCT, UUID(cats["Kawiarnie"]))
    assert (food.expense, food.count) == (Decimal("79.00"), 3)
    assert (cafe.expense, cafe.count) == (Decimal("14.00"), 1)

    r = await client.get(f"/transactions?category_id={cats['Jedzenie']}", headers=headers)
    assert sorted(t["amount"] for t in r.json()["items"]) == ["14.00", "20.00", "45.00"]


async def test_breakdown_by_main_and_inside_category(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, _, cats = await food_month(client, make_user)
    async with session_factory() as s:
        main = await analytics.breakdown_by_category(s, uid, *OCT, TransactionType.EXPENSE)
        inside = await analytics.breakdown_by_category(
            s, uid, *OCT, TransactionType.EXPENSE, UUID(cats["Jedzenie"])
        )
    assert [(r.name, r.total, r.count) for r in main] == [
        ("Transport", Decimal("200.00"), 1),
        ("Jedzenie", Decimal("79.00"), 3),
    ]
    assert [(r.name, r.total) for r in inside] == [
        ("Restauracje", Decimal("45.00")),
        ("Jedzenie", Decimal("20.00")),
        ("Kawiarnie", Decimal("14.00")),
    ]


async def test_budget_counts_subcategories_and_rejects_subcategory_budget(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, _, cats = await food_month(client, make_user)
    async with session_factory() as s:
        s.add(Budget(user_id=uid, category_id=UUID(cats["Jedzenie"]), amount=Decimal("100.00")))
        s.add(Budget(user_id=uid, category_id=UUID(cats["Transport"]), amount=Decimal("300.00")))
        await s.commit()
        usage = await analytics.budget_usage(s, uid, *OCT)
        assert [(u.category_name, u.spent) for u in usage] == [
            ("Jedzenie", Decimal("79.00")),
            ("Transport", Decimal("200.00")),
        ]
        with pytest.raises(InvalidInputError) as exc:
            await svc.propose_budget(s, uid, "Kawiarnie", Decimal("50.00"))
    assert "Jedzenie" in exc.value.message


async def test_proposal_with_subcategory_and_edit_to_other_subcategory(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    item = ProposedTransaction.model_validate(
        {"type": "expense", "amount": "89.00", "category": "przejazdy", "occurred_on": "2026-11-17"}
    )
    async with session_factory() as s:
        proposal = await svc.propose_transactions(s, uid, [item])
        await s.commit()
    first = proposal.payload["items"][0]
    assert (first["category"], first["subcategory"]) == ("Podróże", "Przejazdy")
    assert first["category_id"] == cats["Przejazdy"]

    edited = {
        "type": "expense",
        "amount": "89.00",
        "category_id": cats["Komunikacja miejska"],
        "occurred_on": "2026-11-17",
    }
    r = await client.post(
        f"/proposals/{proposal.id}/confirm", json={"items": [edited]}, headers=headers
    )
    assert r.status_code == 200, r.text
    saved = r.json()["proposal"]["payload"]
    assert (saved["items"][0]["category"], saved["items"][0]["subcategory"]) == (
        "Transport",
        "Komunikacja miejska",
    )
    assert saved["original_items"][0]["subcategory"] == "Przejazdy"


async def test_other_users_subcategory_is_rejected(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, headers, _ = await make_user()
    _, _, other = await make_user()
    r = await client.post(
        "/transactions",
        json={
            "type": "expense",
            "amount": "10.00",
            "category_id": other["Kawiarnie"],
            "occurred_on": "2026-11-17",
        },
        headers=headers,
    )
    assert r.status_code == 422
