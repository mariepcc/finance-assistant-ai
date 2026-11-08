from httpx import AsyncClient

from tests.conftest import Onboarded


async def test_users_cannot_access_each_other(client: AsyncClient, onboarded: Onboarded) -> None:
    alice, alice_cats = await onboarded()
    bob, bob_cats = await onboarded()
    body = {
        "type": "expense",
        "amount": "12.50",
        "category_id": alice_cats["Jedzenie"],
        "occurred_on": "2026-11-05",
    }
    tx = (await client.post("/transactions", json=body, headers=alice)).json()

    assert (await client.get("/transactions", headers=bob)).json()["items"] == []
    assert (await client.get(f"/transactions/{tx['id']}", headers=bob)).status_code == 404
    patch = await client.patch(f"/transactions/{tx['id']}", json={"amount": "1.00"}, headers=bob)
    assert patch.status_code == 404
    assert (await client.delete(f"/transactions/{tx['id']}", headers=bob)).status_code == 404

    assert (await client.post("/transactions", json=body, headers=bob)).status_code == 422
    own = (
        await client.post(
            "/transactions", json=body | {"category_id": bob_cats["Jedzenie"]}, headers=bob
        )
    ).json()
    r = await client.patch(
        f"/transactions/{own['id']}", json={"category_id": alice_cats["Jedzenie"]}, headers=bob
    )
    assert r.status_code == 422

    still = (await client.get(f"/transactions/{tx['id']}", headers=alice)).json()
    assert still["amount"] == "12.50"

    alice_cat_ids = set(alice_cats.values())
    bob_listing = (await client.get("/categories", headers=bob)).json()
    assert alice_cat_ids.isdisjoint({c["id"] for c in bob_listing})
