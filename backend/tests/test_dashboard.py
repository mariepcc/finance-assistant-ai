from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Budget
from tests.conftest import MakeUser

Factory = async_sessionmaker[AsyncSession]
TODAY = date.today()
THIS_MONTH = TODAY.replace(day=1)
LAST_MONTH = (THIS_MONTH - timedelta(days=1)).replace(day=1)
BEFORE_LAST = (LAST_MONTH - timedelta(days=1)).replace(day=1)


def key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


async def add(
    client: AsyncClient,
    headers: dict[str, str],
    category_id: str,
    amount: str,
    day: date,
    type: str = "expense",
) -> None:
    r = await client.post(
        "/transactions",
        json={
            "type": type,
            "amount": amount,
            "category_id": category_id,
            "occurred_on": day.isoformat(),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text


async def test_past_month_totals_daily_and_categories(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    await add(client, headers, cats["Wynagrodzenie"], "5000.00", LAST_MONTH, "income")
    await add(client, headers, cats["Restauracje"], "45.00", LAST_MONTH)
    await add(client, headers, cats["Kawiarnie"], "15.00", LAST_MONTH + timedelta(days=1))
    await add(client, headers, cats["Jedzenie"], "20.00", LAST_MONTH + timedelta(days=2))
    await add(client, headers, cats["Paliwo"], "200.00", LAST_MONTH + timedelta(days=2))
    await add(client, headers, cats["Paliwo"], "100.00", BEFORE_LAST)
    async with session_factory() as s:
        s.add(Budget(user_id=uid, category_id=UUID(cats["Jedzenie"]), amount=Decimal("100.00")))
        s.add(Budget(user_id=uid, category_id=UUID(cats["Transport"]), amount=Decimal("150.00")))
        await s.commit()

    r = await client.get(f"/dashboard?month={key(LAST_MONTH)}", headers=headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["income"], d["expense"], d["balance"]) == ("5000.00", "280.00", "4720.00")
    assert d["is_current"] is False and d["forecast"] is None and d["upcoming"] == []
    assert len(d["daily"]) == d["days_in_month"]
    assert d["daily"][:3] == ["45.00", "60.00", "280.00"]
    assert d["daily"][-1] == "280.00"
    assert d["previous_expense_total"] == "100.00"
    assert d["expense_change_pct"] == "180.0"

    cats_out = [(c["name"], c["amount"], c["share_pct"]) for c in d["categories"]]
    assert cats_out == [("Transport", "200.00", "71.4"), ("Jedzenie", "80.00", "28.6")]
    food = d["categories"][1]
    assert [(s["name"], s["amount"]) for s in food["subcategories"]] == [
        ("Restauracje", "45.00"),
        ("Kawiarnie", "15.00"),
        ("Pozostałe", "20.00"),
    ]
    assert food["color"] is not None

    statuses = {b["category"]: (b["used_pct"], b["status"]) for b in d["budgets"]}
    assert statuses == {"Jedzenie": ("80.0", "warning"), "Transport": ("133.3", "exceeded")}


async def test_current_month_has_upcoming_and_forecast(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, headers, cats = await make_user()
    await add(client, headers, cats["Spożywcze"], "30.00", THIS_MONTH)
    soon = TODAY + timedelta(days=3)
    late = TODAY + timedelta(days=40)
    for name, day in (("Netflix", soon), ("Daleko", late)):
        r = await client.post(
            "/recurring",
            json={
                "amount": "43.00",
                "category_id": cats["Streaming"],
                "name": name,
                "frequency": "yearly",
                "day_of_month": day.day,
                "month": day.month,
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text

    d = (await client.get("/dashboard", headers=headers)).json()
    assert d["is_current"] is True
    assert d["month"] == key(TODAY)
    assert len(d["daily"]) == TODAY.day
    assert [u["name"] for u in d["upcoming"]] == ["Netflix"]
    assert d["forecast"] is not None
    assert Decimal(d["forecast"]["low"]) <= Decimal(d["forecast"]["typical"])


async def test_isolation_and_validation(client: AsyncClient, make_user: MakeUser) -> None:
    _, headers, cats = await make_user()
    _, other_headers, _ = await make_user()
    await add(client, headers, cats["Paliwo"], "200.00", THIS_MONTH)

    d = (await client.get("/dashboard", headers=other_headers)).json()
    assert (d["expense"], d["categories"], d["forecast"]) == ("0.00", [], None)

    future = (TODAY.replace(day=28) + timedelta(days=10)).replace(day=1)
    for bad in ("2026-13", "26-11", key(future)):
        r = await client.get(f"/dashboard?month={bad}", headers=headers)
        assert r.status_code == 422, bad
