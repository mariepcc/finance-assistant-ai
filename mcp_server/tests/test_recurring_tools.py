from datetime import date, timedelta
from decimal import Decimal

from app.db import get_sessionmaker
from app.models import RecurringFrequency, RecurringRule, Transaction
from sqlalchemy import select

from tests.conftest import ClientAs, MakeUser, UserData, call


async def add_rule(user: UserData, name: str, amount: str, category: str, **kw: object) -> None:
    async with get_sessionmaker()() as s:
        s.add(
            RecurringRule(
                user_id=user.id,
                type=kw.get("type", "expense"),
                amount=Decimal(amount),
                currency="PLN",
                category_id=user.categories[category],
                name=name,
                frequency=kw.get("frequency", RecurringFrequency.MONTHLY),
                day_of_month=kw.get("day", 12),
                month=kw.get("month"),
                next_due_on=kw.get("next_due_on", date.today() + timedelta(days=3)),
                active=kw.get("active", True),
            )
        )
        await s.commit()


async def test_list_recurring_with_monthly_totals(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    other = await make_user()
    await add_rule(user, "Spotify", "23.99", "Streaming")
    await add_rule(user, "OC", "600.00", "Ubezpieczenia", frequency="yearly", day=5, month=3)
    await add_rule(user, "pensja", "6500.00", "Wynagrodzenie", type="income", day=10)
    await add_rule(user, "Netflix", "43.00", "Streaming", active=False)
    await add_rule(other, "Obcy", "999.00", "Streaming")

    async with client_as(user.id) as c:
        data = await call(c, "list_recurring")

    assert (data["active_count"], data["paused_count"]) == (3, 1)
    assert (data["monthly_expense_total"], data["monthly_income_total"]) == ("73.99", "6500.00")
    oc = next(p for p in data["payments"] if p["name"] == "OC")
    assert (oc["category"], oc["subcategory"], oc["monthly_amount"]) == (
        "Rachunki",
        "Ubezpieczenia",
        "50.00",
    )
    assert "Obcy" not in {p["name"] for p in data["payments"]}


async def test_tool_context_books_due_payments(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    due = date.today() - timedelta(days=1)
    await add_rule(user, "Spotify", "23.99", "Streaming", day=due.day, next_due_on=due)

    async with client_as(user.id) as c:
        search = await call(c, "search_transactions", text="Spotify")

    assert search["matched_count"] == 1
    async with get_sessionmaker()() as s:
        tx = await s.scalar(select(Transaction).where(Transaction.user_id == user.id))
    assert tx is not None and tx.occurred_on == due


async def test_propose_recurring_does_not_save(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    async with client_as(user.id) as c:
        data = await call(
            c,
            "propose_recurring",
            name="Ubezpieczenie OC",
            amount="840.00",
            category="Ubezpieczenia",
            frequency="yearly",
            day_of_month=5,
            month=3,
        )
        missing_month = await c.call_tool(
            "propose_recurring",
            {
                "name": "X",
                "amount": "10.00",
                "category": "Streaming",
                "frequency": "yearly",
                "day_of_month": 5,
            },
            raise_on_error=False,
        )

    assert data["status"] == "pending"
    assert (data["category"], data["subcategory"]) == ("Rachunki", "Ubezpieczenia")
    assert data["monthly_amount"] == "70.00"
    assert date.fromisoformat(data["first_payment_on"]).month == 3
    assert missing_month.is_error
    async with get_sessionmaker()() as s:
        assert (await s.scalars(select(RecurringRule))).all() == []
