from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import RecurringFrequency, RecurringRule, Transaction
from app.schemas.proposal import ProposedRecurring
from app.services import proposals as proposals_service
from app.services import recurring as svc
from tests.conftest import MakeUser

Factory = async_sessionmaker[AsyncSession]
MONTHLY = RecurringFrequency.MONTHLY
YEARLY = RecurringFrequency.YEARLY


def test_due_dates_clamp_to_month_end_and_return_to_day() -> None:
    assert svc.due_on_or_after(MONTHLY, 31, None, date(2027, 2, 1)) == date(2027, 2, 28)
    assert svc.due_on_or_after(MONTHLY, 31, None, date(2027, 3, 1)) == date(2027, 3, 31)
    assert svc.due_on_or_after(MONTHLY, 12, None, date(2026, 12, 13)) == date(2027, 1, 12)
    assert svc.due_on_or_after(MONTHLY, 22, None, date(2026, 11, 22)) == date(2026, 11, 22)
    assert svc.due_on_or_after(YEARLY, 29, 2, date(2027, 1, 1)) == date(2027, 2, 28)
    assert svc.due_on_or_after(YEARLY, 29, 2, date(2027, 3, 1)) == date(2028, 2, 29)
    assert svc.due_on_or_after(YEARLY, 5, 3, date(2026, 11, 22)) == date(2027, 3, 5)


async def rule_for(
    session: AsyncSession, user_id: UUID, category_id: str, next_due_on: date
) -> RecurringRule:
    rule = RecurringRule(
        user_id=user_id,
        type="expense",
        amount=Decimal("23.99"),
        currency="PLN",
        category_id=UUID(category_id),
        name="Spotify",
        frequency=MONTHLY,
        day_of_month=next_due_on.day,
        month=None,
        next_due_on=next_due_on,
        active=True,
    )
    session.add(rule)
    await session.flush()
    return rule


async def booked(session: AsyncSession, rule_id: UUID) -> list[date]:
    rows = await session.scalars(
        select(Transaction.occurred_on)
        .where(Transaction.recurring_id == rule_id)
        .order_by(Transaction.occurred_on)
    )
    return list(rows.all())


async def test_materialize_books_missed_payments_once(
    make_user: MakeUser, session_factory: Factory
) -> None:
    uid, _, cats = await make_user()
    async with session_factory() as s:
        rule = await rule_for(s, uid, cats["Streaming"], date(2026, 9, 12))
        assert await svc.materialize_due(s, uid, date(2026, 11, 22)) == 3
        assert await svc.materialize_due(s, uid, date(2026, 11, 22)) == 0
        await s.commit()
        assert await booked(s, rule.id) == [
            date(2026, 9, 12),
            date(2026, 10, 12),
            date(2026, 11, 12),
        ]
        assert rule.next_due_on == date(2026, 12, 12)
        tx = await s.scalar(select(Transaction).where(Transaction.recurring_id == rule.id))
        assert tx is not None
        assert (tx.source, tx.note, tx.amount) == ("recurring", "Spotify", Decimal("23.99"))


async def test_paused_rule_skips_and_resume_starts_from_today(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    today = date.today()
    async with session_factory() as s:
        rule = await rule_for(s, uid, cats["Streaming"], today - timedelta(days=40))
        rule.active = False
        await s.commit()
        rule_id = rule.id

    r = await client.get("/transactions", headers=headers)
    assert r.json()["items"] == []

    r = await client.patch(f"/recurring/{rule_id}", json={"active": True}, headers=headers)
    assert r.status_code == 200, r.text
    assert date.fromisoformat(r.json()["next_due_on"]) >= today
    async with session_factory() as s:
        assert all(d >= today for d in await booked(s, rule_id))


async def test_crud_and_monthly_totals(client: AsyncClient, make_user: MakeUser) -> None:
    _, headers, cats = await make_user()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    spotify = {
        "amount": "23.99",
        "category_id": cats["Streaming"],
        "name": "Spotify",
        "frequency": "monthly",
        "day_of_month": tomorrow.day,
    }
    insurance = {
        "amount": "600.00",
        "category_id": cats["Ubezpieczenia"],
        "name": "OC",
        "frequency": "yearly",
        "day_of_month": 5,
        "month": 3,
    }
    salary = {
        "type": "income",
        "amount": "6500.00",
        "category_id": cats["Wynagrodzenie"],
        "name": "pensja",
        "frequency": "monthly",
        "day_of_month": 10,
    }
    for body in (spotify, insurance, salary):
        r = await client.post("/recurring", json=body, headers=headers)
        assert r.status_code == 201, r.text

    r = await client.get("/recurring", headers=headers)
    data = r.json()
    assert (data["monthly_expense"], data["monthly_income"]) == ("73.99", "6500.00")
    oc = next(i for i in data["items"] if i["name"] == "OC")
    assert oc["monthly_amount"] == "50.00"

    spotify_id = next(i["id"] for i in data["items"] if i["name"] == "Spotify")
    r = await client.patch(f"/recurring/{spotify_id}", json={"amount": "29.99"}, headers=headers)
    assert r.json()["amount"] == "29.99"
    r = await client.patch(f"/recurring/{spotify_id}", json={"active": False}, headers=headers)
    assert r.json()["active"] is False
    r = await client.get("/recurring", headers=headers)
    assert r.json()["monthly_expense"] == "50.00"

    r = await client.delete(f"/recurring/{spotify_id}", headers=headers)
    assert r.status_code == 204
    r = await client.get(f"/recurring/{spotify_id}", headers=headers)
    assert r.status_code == 404


async def test_payment_due_today_is_booked_immediately(
    client: AsyncClient, make_user: MakeUser
) -> None:
    _, headers, cats = await make_user()
    today = date.today()
    body = {
        "amount": "43.00",
        "category_id": cats["Streaming"],
        "name": "Netflix",
        "frequency": "monthly",
        "day_of_month": today.day,
    }
    r = await client.post("/recurring", json=body, headers=headers)
    rule = r.json()
    assert date.fromisoformat(rule["next_due_on"]) > today
    items = (await client.get("/transactions", headers=headers)).json()["items"]
    assert [(t["note"], t["occurred_on"], t["recurring_id"]) for t in items] == [
        ("Netflix", today.isoformat(), rule["id"])
    ]


async def test_validation_and_isolation(client: AsyncClient, make_user: MakeUser) -> None:
    _, headers, cats = await make_user()
    _, other_headers, other_cats = await make_user()
    base = {"amount": "10.00", "name": "X", "frequency": "monthly", "day_of_month": 3}

    r = await client.post(
        "/recurring", json={**base, "category_id": other_cats["Streaming"]}, headers=headers
    )
    assert r.status_code == 422
    r = await client.post(
        "/recurring",
        json={**base, "category_id": cats["Streaming"], "frequency": "yearly"},
        headers=headers,
    )
    assert r.status_code == 422
    r = await client.post(
        "/recurring", json={**base, "category_id": cats["Wynagrodzenie"]}, headers=headers
    )
    assert r.status_code == 422

    r = await client.post(
        "/recurring", json={**base, "category_id": cats["Streaming"]}, headers=headers
    )
    rule_id = r.json()["id"]
    assert (await client.get(f"/recurring/{rule_id}", headers=other_headers)).status_code == 404
    r = await client.patch(f"/recurring/{rule_id}", json={"amount": "1.00"}, headers=other_headers)
    assert r.status_code == 404
    assert (await client.get("/recurring", headers=other_headers)).json()["items"] == []


async def test_proposal_confirm_with_edit_creates_rule(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    today = date.today()
    item = ProposedRecurring.model_validate(
        {
            "amount": "43.00",
            "category": "streaming",
            "name": "Netflix",
            "frequency": "monthly",
            "day_of_month": 5,
        }
    )
    async with session_factory() as s:
        proposal = await proposals_service.propose_recurring(s, uid, item, today)
        await s.commit()
    payload = proposal.payload
    assert (payload["category"], payload["subcategory"]) == ("Rozrywka", "Streaming")
    assert date.fromisoformat(payload["first_payment_on"]) >= today

    edited = {
        "amount": "49.00",
        "category_id": cats["Streaming"],
        "name": "Netflix",
        "frequency": "monthly",
        "day_of_month": today.day,
    }
    r = await client.post(
        f"/proposals/{proposal.id}/confirm", json={"recurring": edited}, headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recurring"]["amount"] == "49.00"
    assert body["proposal"]["payload"]["original"]["amount"] == "43.00"
    async with session_factory() as s:
        count = await s.scalar(
            select(func.count()).where(Transaction.recurring_id == UUID(body["recurring"]["id"]))
        )
    assert count == 1


async def test_recurring_edits_rejected_on_transaction_proposal(
    client: AsyncClient, make_user: MakeUser, session_factory: Factory
) -> None:
    uid, headers, cats = await make_user()
    item = ProposedRecurring.model_validate(
        {
            "amount": "43.00",
            "category": "Streaming",
            "name": "N",
            "frequency": "monthly",
            "day_of_month": 5,
        }
    )
    async with session_factory() as s:
        proposal = await proposals_service.propose_recurring(s, uid, item, date.today())
        await s.commit()
    r = await client.post(
        f"/proposals/{proposal.id}/confirm", json={"amount": "10.00"}, headers=headers
    )
    assert r.status_code == 422
