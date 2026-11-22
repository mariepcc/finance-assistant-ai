from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from tests.conftest import MakeUser

TODAY = date.today()
THIS_MONTH = TODAY.replace(day=1)
LAST_MONTH = (THIS_MONTH - timedelta(days=1)).replace(day=1)
TWO_AGO = (LAST_MONTH - timedelta(days=1)).replace(day=1)


def key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


async def add(
    client: AsyncClient, headers: dict[str, str], category_id: str, amount: str, day: date
) -> None:
    r = await client.post(
        "/transactions",
        json={
            "type": "expense",
            "amount": amount,
            "category_id": category_id,
            "occurred_on": day.isoformat(),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text


async def put(client: AsyncClient, headers: dict[str, str], category_id: str, amount: str) -> int:
    r = await client.put(f"/budgets/{category_id}", json={"amount": amount}, headers=headers)
    return r.status_code


async def test_overview_usage_average_and_forecast(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, headers, cats = await make_user()
    await add(client, headers, cats["Restauracje"], "300.00", TWO_AGO)
    await add(client, headers, cats["Spożywcze"], "100.00", LAST_MONTH)
    await add(client, headers, cats["Kawiarnie"], "90.00", THIS_MONTH)
    await add(client, headers, cats["Paliwo"], "260.00", THIS_MONTH)
    assert await put(client, headers, cats["Jedzenie"], "100.00") == 200
    assert await put(client, headers, cats["Transport"], "250.00") == 200

    d = (await client.get("/budgets", headers=headers)).json()
    assert d["is_current"] is True
    assert (d["total_limit"], d["total_spent"]) == ("350.00", "350.00")
    items = {i["category"]: i for i in d["items"]}
    assert (items["Jedzenie"]["spent"], items["Jedzenie"]["status"]) == ("90.00", "warning")
    assert (items["Transport"]["remaining"], items["Transport"]["status"]) == ("-10.00", "exceeded")
    assert items["Jedzenie"]["average_monthly"] == "200.00"
    assert items["Jedzenie"]["forecast_typical"] is not None

    past = (await client.get(f"/budgets?month={key(LAST_MONTH)}", headers=headers)).json()
    past_items = {i["category"]: i for i in past["items"]}
    assert past_items["Jedzenie"]["forecast_typical"] is None
    assert past_items["Jedzenie"]["spent"] == "100.00"
    assert past_items["Jedzenie"]["average_monthly"] == "300.00"

    suggestions = {
        s["category"]: s for s in (await client.get("/budgets/suggestions", headers=headers)).json()
    }
    assert suggestions["Jedzenie"]["has_budget"] is True
    assert suggestions["Zakupy"]["has_budget"] is False
    assert suggestions["Zakupy"]["average_monthly"] == "0.00"
    assert "Kawiarnie" not in suggestions


async def test_put_updates_single_record_and_delete(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, headers, cats = await make_user()
    assert await put(client, headers, cats["Zakupy"], "400.00") == 200
    assert await put(client, headers, cats["Zakupy"], "550.00") == 200
    items = (await client.get("/budgets", headers=headers)).json()["items"]
    assert [(i["category"], i["limit"]) for i in items] == [("Zakupy", "550.00")]

    r = await client.delete(f"/budgets/{cats['Zakupy']}", headers=headers)
    assert r.status_code == 204
    r = await client.delete(f"/budgets/{cats['Zakupy']}", headers=headers)
    assert r.status_code == 404
    assert (await client.get("/budgets", headers=headers)).json()["items"] == []


async def test_validation_and_isolation(client: AsyncClient, make_user: MakeUser) -> None:
    _, headers, cats = await make_user()
    _, other_headers, other_cats = await make_user()

    r = await client.put(f"/budgets/{cats['Kawiarnie']}", json={"amount": "50.00"}, headers=headers)
    assert r.status_code == 422
    assert "Jedzenie" in r.json()["detail"]
    assert await put(client, headers, cats["Wynagrodzenie"], "50.00") == 422
    assert await put(client, headers, other_cats["Jedzenie"], "50.00") == 422
    assert await put(client, headers, cats["Jedzenie"], "0") == 422

    assert await put(client, headers, cats["Jedzenie"], "500.00") == 200
    assert (await client.get("/budgets", headers=other_headers)).json()["items"] == []
    r = await client.delete(f"/budgets/{cats['Jedzenie']}", headers=other_headers)
    assert r.status_code == 404
    assert Decimal((await client.get("/budgets", headers=headers)).json()["total_limit"]) == 500
