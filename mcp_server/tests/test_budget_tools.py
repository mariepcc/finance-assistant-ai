from app.db import get_sessionmaker
from app.models import Budget, Proposal
from sqlalchemy import func, select

from tests.conftest import ClientAs, MakeUser, call


async def test_budget_status(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.budget("Jedzenie", "500.00")
    await user.budget("Transport", "100.00")
    await user.budget("Rozrywka", "50.00")
    await user.add("200.00", "Jedzenie", "2026-11-02")
    await user.add("85.00", "Transport", "2026-11-03")
    await user.add("50.01", "Rozrywka", "2026-11-04")
    await user.add("1000.00", "Jedzenie", "2026-10-30")

    async with client_as(user.id) as c:
        data = await call(c, "get_budget_status", month="2026-11")
        bad = await c.call_tool("get_budget_status", {"month": "listopad"}, raise_on_error=False)

    lines = {b["category"]: b for b in data["budgets"]}
    assert (
        lines["Jedzenie"]["spent"],
        lines["Jedzenie"]["used_pct"],
        lines["Jedzenie"]["status"],
    ) == (
        "200.00",
        "40.0",
        "ok",
    )
    assert (lines["Transport"]["remaining"], lines["Transport"]["status"]) == ("15.00", "warning")
    assert (lines["Rozrywka"]["remaining"], lines["Rozrywka"]["status"]) == ("-0.01", "exceeded")
    assert (data["total_limit"], data["total_spent"]) == ("650.00", "335.01")
    assert bad.is_error


async def test_propose_budget(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.budget("Jedzenie", "500.00")
    async with client_as(user.id) as c:
        update = await call(c, "propose_budget", category="jedzenie", amount="650.5")
        new = await call(c, "propose_budget", category="Transport", amount="120")
        income = await c.call_tool(
            "propose_budget", {"category": "Wynagrodzenie", "amount": "1"}, raise_on_error=False
        )

    assert (update["category"], update["amount"], update["previous_amount"]) == (
        "Jedzenie",
        "650.50",
        "500.00",
    )
    assert new["previous_amount"] is None and new["status"] == "pending"
    assert income.is_error
    async with get_sessionmaker()() as s:
        assert await s.scalar(select(func.count()).select_from(Proposal)) == 2
        amounts = (await s.scalars(select(Budget.amount))).all()
    assert [str(a) for a in amounts] == ["500.00"]
