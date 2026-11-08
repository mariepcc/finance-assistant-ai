import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import AuthHeaders, Onboarded


def _tx(category_id: str, **overrides: Any) -> dict[str, Any]:
    body = {
        "type": "expense",
        "amount": "55.00",
        "category_id": category_id,
        "occurred_on": "2026-11-05",
        "note": "zakupy w Biedronce",
    }
    return body | overrides


async def test_crud_flow(client: AsyncClient, onboarded: Onboarded) -> None:
    headers, cats = await onboarded()
    r = await client.post("/transactions", json=_tx(cats["Jedzenie"]), headers=headers)
    assert r.status_code == 201, r.text
    tx = r.json()
    assert tx["amount"] == "55.00"
    assert tx["currency"] == "PLN"
    assert tx["source"] == "manual"

    got = (await client.get(f"/transactions/{tx['id']}", headers=headers)).json()
    assert got == tx

    r = await client.patch(
        f"/transactions/{tx['id']}",
        json={"amount": "4.40", "category_id": cats["Transport"], "note": None},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "4.40"
    assert r.json()["note"] is None

    assert (await client.delete(f"/transactions/{tx['id']}", headers=headers)).status_code == 204
    assert (await client.get(f"/transactions/{tx['id']}", headers=headers)).status_code == 404


async def test_requires_consent(client: AsyncClient, auth: AuthHeaders) -> None:
    r = await client.post("/transactions", json=_tx(str(uuid.uuid4())), headers=auth(uuid.uuid4()))
    assert r.status_code == 403


@pytest.mark.parametrize("amount", ["0", "-10.00", "1.234", "10000000000.00", "abc"])
async def test_rejects_invalid_amount(
    client: AsyncClient, onboarded: Onboarded, amount: str
) -> None:
    headers, cats = await onboarded()
    r = await client.post(
        "/transactions", json=_tx(cats["Jedzenie"], amount=amount), headers=headers
    )
    assert r.status_code == 422


async def test_category_must_match_type(client: AsyncClient, onboarded: Onboarded) -> None:
    headers, cats = await onboarded()
    r = await client.post(
        "/transactions", json=_tx(cats["Wynagrodzenie"], type="expense"), headers=headers
    )
    assert r.status_code == 422
    ok = await client.post(
        "/transactions", json=_tx(cats["Wynagrodzenie"], type="income"), headers=headers
    )
    assert ok.status_code == 201
    r = await client.patch(
        f"/transactions/{ok.json()['id']}", json={"type": "expense"}, headers=headers
    )
    assert r.status_code == 422


async def test_patch_rejects_null_required_fields(
    client: AsyncClient, onboarded: Onboarded
) -> None:
    headers, cats = await onboarded()
    tx = (await client.post("/transactions", json=_tx(cats["Jedzenie"]), headers=headers)).json()
    for field in ("amount", "type", "category_id", "occurred_on"):
        r = await client.patch(f"/transactions/{tx['id']}", json={field: None}, headers=headers)
        assert r.status_code == 422, field


async def test_filters_and_search(client: AsyncClient, onboarded: Onboarded) -> None:
    headers, cats = await onboarded()
    for body in (
        _tx(cats["Jedzenie"], occurred_on="2026-10-30", note="kawa"),
        _tx(cats["Transport"], occurred_on="2026-11-02", note="bilet 100%"),
        _tx(cats["Wynagrodzenie"], type="income", amount="5000.00", occurred_on="2026-11-01"),
    ):
        assert (await client.post("/transactions", json=body, headers=headers)).status_code == 201

    async def notes(query: str) -> list[str | None]:
        page = (await client.get(f"/transactions?{query}", headers=headers)).json()
        return [t["note"] for t in page["items"]]

    assert len(await notes("")) == 3
    assert await notes("type=income") == ["zakupy w Biedronce"]
    assert await notes("from=2026-11-01&to=2026-11-30&type=expense") == ["bilet 100%"]
    assert await notes(f"category_id={cats['Jedzenie']}") == ["kawa"]
    assert await notes("q=KAWA") == ["kawa"]
    assert await notes("q=%25") == ["bilet 100%"]


async def test_cursor_pagination(client: AsyncClient, onboarded: Onboarded) -> None:
    headers, cats = await onboarded()
    for day in range(1, 6):
        body = _tx(cats["Jedzenie"], occurred_on=f"2026-11-0{day}", note=f"d{day}")
        await client.post("/transactions", json=body, headers=headers)

    seen: list[str] = []
    cursor: str | None = None
    while True:
        url = "/transactions?limit=2" + (f"&cursor={cursor}" if cursor else "")
        page = (await client.get(url, headers=headers)).json()
        seen += [t["note"] for t in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["d5", "d4", "d3", "d2", "d1"]
    bad = await client.get("/transactions?cursor=zly", headers=headers)
    assert bad.status_code == 422
