from app.db import get_sessionmaker
from app.models import Proposal, Transaction, TransactionType
from sqlalchemy import func, select

from tests.conftest import ClientAs, MakeUser, call


async def test_search_filters_and_totals(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("14.00", "Jedzenie", "2026-11-01", note="kawa")
    await user.add("32.50", "Jedzenie", "2026-11-02", note="obiad")
    await user.add("4.40", "Transport", "2026-11-03", note="bilet")
    await user.add("120.00", "Zakupy", "2026-10-15")
    await user.add("5000.00", "Wynagrodzenie", "2026-11-10", type=TransactionType.INCOME)

    async with client_as(user.id) as c:
        nov = await call(c, "search_transactions", date_from="2026-11-01", date_to="2026-11-30")
        food = await call(c, "search_transactions", category="jedzenie", limit=1)
        big = await call(
            c, "search_transactions", min_amount="20", max_amount="200", type="expense"
        )
        note = await call(c, "search_transactions", text="KAWA")

    assert (nov["matched_count"], nov["matched_expense"], nov["matched_income"]) == (
        4,
        "50.90",
        "5000.00",
    )
    assert nov["transactions"][0]["occurred_on"] == "2026-11-10"
    assert food["matched_count"] == 2 and food["returned_count"] == 1 and food["truncated"]
    assert food["matched_expense"] == "46.50"
    assert food["transactions"][0]["category"] == "Jedzenie"
    assert sorted(t["amount"] for t in big["transactions"]) == ["120.00", "32.50"]
    assert [t["note"] for t in note["transactions"]] == ["kawa"]


async def test_unknown_category_lists_available(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    async with client_as(user.id) as c:
        result = await c.call_tool(
            "search_transactions", {"category": "Kosmos"}, raise_on_error=False
        )
    assert result.is_error
    assert "Dostępne" in str(result.content) and "Jedzenie" in str(result.content)


async def test_propose_transaction_does_not_write(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    items = [
        {"type": "expense", "amount": "14", "category": "jedzenie", "occurred_on": "2026-11-08"},
        {
            "type": "expense",
            "amount": "4.4",
            "category": "Transport",
            "occurred_on": "2026-11-08",
            "note": "bilet",
        },
    ]
    async with client_as(user.id) as c:
        data = await call(c, "propose_transaction", items=items)

    assert data["status"] == "pending" and data["requires_user_confirmation"]
    assert [(i["amount"], i["category"]) for i in data["items"]] == [
        ("14.00", "Jedzenie"),
        ("4.40", "Transport"),
    ]
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Transaction)) == 0
        proposal = await s.get(Proposal, data["proposal_id"])
    assert proposal is not None and proposal.user_id == user.id and proposal.status == "pending"


async def test_propose_transaction_validation(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    async with client_as(user.id) as c:
        wrong_kind = await c.call_tool(
            "propose_transaction",
            {
                "items": [
                    {
                        "type": "income",
                        "amount": "10",
                        "category": "Jedzenie",
                        "occurred_on": "2026-11-08",
                    }
                ]
            },
            raise_on_error=False,
        )
        negative = await c.call_tool(
            "propose_transaction",
            {
                "items": [
                    {
                        "type": "expense",
                        "amount": "-5",
                        "category": "Jedzenie",
                        "occurred_on": "2026-11-08",
                    }
                ]
            },
            raise_on_error=False,
        )
        empty = await c.call_tool("propose_transaction", {"items": []}, raise_on_error=False)
    assert wrong_kind.is_error and negative.is_error and empty.is_error
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Proposal)) == 0
