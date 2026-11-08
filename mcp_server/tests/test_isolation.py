from tests.conftest import ClientAs, MakeUser, call


async def test_tools_only_see_own_data(client_as: ClientAs, make_user: MakeUser) -> None:
    alice = await make_user()
    bob = await make_user()
    await alice.add("123.45", "Jedzenie", "2026-11-05", note="tajne")
    await alice.budget("Jedzenie", "300.00")

    async with client_as(bob.id) as c:
        search = await call(c, "search_transactions")
        summary = await call(c, "get_summary", date_from="2026-01-01", date_to="2026-12-31")
        budgets = await call(c, "get_budget_status", month="2026-11")
        cats = await call(c, "list_categories")

    assert search["matched_count"] == 0 and search["transactions"] == []
    assert summary["expense"] == "0.00"
    assert budgets["budgets"] == []
    assert len(cats["categories"]) == 10
