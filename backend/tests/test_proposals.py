from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import ConsentRequiredError, InvalidInputError
from app.models import Budget, Proposal, Transaction
from app.schemas.proposal import ProposedTransaction
from app.services import proposals as svc
from tests.conftest import AuthHeaders, MakeUser

Factory = async_sessionmaker[AsyncSession]


def _item(**overrides: object) -> ProposedTransaction:
    data: dict[str, object] = {
        "type": "expense",
        "amount": "14.00",
        "category": "jedzenie",
        "occurred_on": "2026-11-08",
        "note": "kawa",
    }
    return ProposedTransaction.model_validate(data | overrides)


async def _count(factory: Factory, model: type[Transaction] | type[Budget]) -> int:
    async with factory() as s:
        return int(await s.scalar(select(func.count()).select_from(model)) or 0)


async def test_propose_and_confirm_transactions(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_transactions(
            s, uid, [_item(), _item(amount="4.40", category="Transport", note=None)]
        )
        await s.commit()
    assert proposal.payload["items"][0]["category"] == "Jedzenie"
    assert proposal.payload["items"][0]["category_id"] == cats["Jedzenie"]
    assert await _count(session_factory, Transaction) == 0

    r = await client.post(f"/proposals/{proposal.id}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["proposal"]["status"] == "confirmed"
    assert [t["amount"] for t in body["transactions"]] == ["14.00", "4.40"]
    assert {t["source"] for t in body["transactions"]} == {"assistant"}

    again = await client.post(f"/proposals/{proposal.id}/confirm", headers=headers)
    assert again.status_code == 409
    assert await _count(session_factory, Transaction) == 2
    async with session_factory() as s:
        linked = await s.scalar(select(func.count()).where(Transaction.proposal_id == proposal.id))
    assert linked == 2


async def test_unknown_category_lists_available(
    make_user: MakeUser, session_factory: Factory
) -> None:
    uid, _, _ = await make_user()
    async with session_factory() as s:
        with pytest.raises(InvalidInputError) as exc:
            await svc.propose_transactions(s, uid, [_item(category="Kosmos")])
    assert "Jedzenie" in exc.value.message
    async with session_factory() as s:
        with pytest.raises(InvalidInputError):
            await svc.propose_transactions(s, uid, [_item(type="income", category="Jedzenie")])


async def test_requires_consent(session_factory: Factory) -> None:
    async with session_factory() as s:
        with pytest.raises(ConsentRequiredError):
            await svc.propose_transactions(s, uuid4(), [_item()])


async def test_reject_and_expire(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, _ = await make_user()
    async with session_factory() as s:
        rejected = await svc.propose_transactions(s, uid, [_item()])
        expired = await svc.propose_transactions(s, uid, [_item()])
        await s.execute(
            update(Proposal)
            .where(Proposal.id == expired.id)
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()

    r = await client.post(f"/proposals/{rejected.id}/reject", headers=headers)
    assert r.json()["status"] == "rejected"
    assert (
        await client.post(f"/proposals/{rejected.id}/confirm", headers=headers)
    ).status_code == 409

    assert (
        await client.post(f"/proposals/{expired.id}/confirm", headers=headers)
    ).status_code == 410
    async with session_factory() as s:
        status = await s.scalar(select(Proposal.status).where(Proposal.id == expired.id))
    assert status == "expired"
    assert await _count(session_factory, Transaction) == 0


async def test_other_user_cannot_confirm(
    client: AsyncClient, make_user: MakeUser, auth: AuthHeaders, session_factory: Factory
) -> None:
    uid, _, _ = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_transactions(s, uid, [_item()])
        await s.commit()
    stranger = auth(uuid4())
    assert (
        await client.post(f"/proposals/{proposal.id}/confirm", headers=stranger)
    ).status_code == 404
    assert (await client.post(f"/proposals/{uuid4()}/confirm", headers=stranger)).status_code == 404


async def test_budget_proposal_creates_then_updates(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    async with session_factory() as s:
        first = await svc.propose_budget(s, uid, "Jedzenie", Decimal("800.00"))
        await s.commit()
    assert first.payload["previous_amount"] is None
    r = await client.post(f"/proposals/{first.id}/confirm", headers=headers)
    assert r.json()["budget"]["amount"] == "800.00"

    async with session_factory() as s:
        second = await svc.propose_budget(s, uid, "Jedzenie", Decimal("650.50"))
        await s.commit()
    assert Decimal(second.payload["previous_amount"]) == Decimal("800.00")
    r = await client.post(f"/proposals/{second.id}/confirm", headers=headers)
    assert r.json()["budget"]["amount"] == "650.50"
    assert await _count(session_factory, Budget) == 1

    async with session_factory() as s:
        with pytest.raises(InvalidInputError):
            await svc.propose_budget(s, uid, "Wynagrodzenie", Decimal("100.00"))


async def test_confirm_with_edited_items(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_transactions(
            s, uid, [_item(), _item(amount="4.40", category="Rozrywka", note="bilet")]
        )
        await s.commit()

    edited = [
        {
            "type": "expense",
            "amount": "4.40",
            "category_id": cats["Transport"],
            "occurred_on": "2026-11-07",
            "note": " bilet na autobus ",
        }
    ]
    r = await client.post(
        f"/proposals/{proposal.id}/confirm", json={"items": edited}, headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [
        (t["amount"], t["category_id"], t["occurred_on"], t["note"]) for t in body["transactions"]
    ] == [("4.40", cats["Transport"], "2026-11-07", "bilet na autobus")]
    payload = body["proposal"]["payload"]
    assert payload["items"][0]["category"] == "Transport"
    assert [i["category"] for i in payload["original_items"]] == ["Jedzenie", "Rozrywka"]
    assert await _count(session_factory, Transaction) == 1


async def test_unchanged_edit_keeps_payload_clean(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_transactions(s, uid, [_item()])
        await s.commit()
    same = [
        {
            "type": "expense",
            "amount": "14",
            "category_id": cats["Jedzenie"],
            "occurred_on": "2026-11-08",
            "note": "kawa",
        }
    ]
    r = await client.post(
        f"/proposals/{proposal.id}/confirm", json={"items": same}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["proposal"]["payload"]["original_items"] is None


async def test_edit_rejects_wrong_category_and_keeps_proposal_pending(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    _, _, other_cats = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_transactions(s, uid, [_item()])
        await s.commit()

    def body(category_id: str, kind: str = "expense") -> dict[str, object]:
        item = {
            "type": kind,
            "amount": "14.00",
            "category_id": category_id,
            "occurred_on": "2026-11-08",
        }
        return {"items": [item]}

    url = f"/proposals/{proposal.id}/confirm"
    assert (
        await client.post(url, json=body(cats["Wynagrodzenie"]), headers=headers)
    ).status_code == 422
    assert (
        await client.post(url, json=body(other_cats["Jedzenie"]), headers=headers)
    ).status_code == 422
    assert (await client.post(url, json={"items": []}, headers=headers)).status_code == 422
    assert (await client.post(url, json={"amount": "5.00"}, headers=headers)).status_code == 422
    assert (
        await client.post(url, json=body(cats["Wynagrodzenie"], "income"), headers=headers)
    ).status_code == 200
    assert await _count(session_factory, Transaction) == 1


async def test_confirm_budget_with_edited_amount(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    async with session_factory() as s:
        proposal = await svc.propose_budget(s, uid, "Jedzenie", Decimal("800.00"))
        await s.commit()
    url = f"/proposals/{proposal.id}/confirm"
    item = {
        "type": "expense",
        "amount": "1",
        "category_id": cats["Jedzenie"],
        "occurred_on": "2026-11-08",
    }
    assert (await client.post(url, json={"items": [item]}, headers=headers)).status_code == 422
    r = await client.post(url, json={"amount": "650.00"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["budget"]["amount"] == "650.00"
    payload = r.json()["proposal"]["payload"]
    assert (payload["amount"], payload["original_amount"]) == ("650.00", "800.00")
