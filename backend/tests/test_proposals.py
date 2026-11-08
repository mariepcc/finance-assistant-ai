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
