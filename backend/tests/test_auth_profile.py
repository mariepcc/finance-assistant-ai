import uuid

from httpx import AsyncClient

from tests.conftest import AuthHeaders, make_token


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.json() == {"status": "ok"}


async def test_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/me")).status_code == 401
    assert (await client.get("/transactions")).status_code == 401


async def test_rejects_bad_tokens(client: AsyncClient) -> None:
    uid = uuid.uuid4()
    for token in (
        make_token(uid, secret="inny-sekret-tez-dlugi-na-32-bajty!!"),
        make_token(uid, aud="anon"),
        make_token(uid, iss="https://evil.example.com/auth/v1"),
        "nie-jwt",
    ):
        r = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


async def test_me_creates_profile_once(client: AsyncClient, auth: AuthHeaders) -> None:
    uid = uuid.uuid4()
    first = (await client.get("/me", headers=auth(uid))).json()
    second = (await client.get("/me", headers=auth(uid))).json()
    assert first["id"] == second["id"] == str(uid)
    assert first["default_currency"] == "PLN"
    assert first["gdpr_consent_at"] is None


async def test_consent_seeds_default_categories_once(
    client: AsyncClient, auth: AuthHeaders
) -> None:
    headers = auth(uuid.uuid4())
    assert (
        await client.post("/me/consent", json={"accepted": False}, headers=headers)
    ).status_code == 422
    for _ in range(2):
        r = await client.post("/me/consent", json={"accepted": True}, headers=headers)
        assert r.status_code == 200
        assert r.json()["gdpr_consent_at"] is not None
    cats = (await client.get("/categories", headers=headers)).json()
    assert len(cats) == 10
    expense = (await client.get("/categories?kind=expense", headers=headers)).json()
    assert {c["kind"] for c in expense} == {"expense"}
    assert "Jedzenie" in {c["name"] for c in expense}


async def test_update_profile_currency(client: AsyncClient, auth: AuthHeaders) -> None:
    headers = auth(uuid.uuid4())
    r = await client.patch("/me", json={"default_currency": "EUR"}, headers=headers)
    assert r.json()["default_currency"] == "EUR"
    r = await client.patch("/me", json={"default_currency": "euro"}, headers=headers)
    assert r.status_code == 422
