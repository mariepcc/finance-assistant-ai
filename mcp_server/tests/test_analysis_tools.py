from app.models import TransactionType

from tests.conftest import ClientAs, MakeUser, call


async def test_summary_and_breakdown(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("0.10", "Jedzenie", "2026-11-01")
    await user.add("0.20", "Jedzenie", "2026-11-02")
    await user.add("29.70", "Transport", "2026-11-03")
    await user.add("70.00", "Rozrywka", "2026-11-04")
    await user.add("3000.00", "Wynagrodzenie", "2026-11-10", type=TransactionType.INCOME)
    await user.add("999.00", "Rozrywka", "2026-12-01")

    async with client_as(user.id) as c:
        summary = await call(c, "get_summary", date_from="2026-11-01", date_to="2026-11-30")
        breakdown = await call(
            c, "get_breakdown_by_category", date_from="2026-11-01", date_to="2026-11-30"
        )
        bad = await c.call_tool(
            "get_summary",
            {"date_from": "2026-11-30", "date_to": "2026-11-01"},
            raise_on_error=False,
        )

    assert summary == {
        "period": {"date_from": "2026-11-01", "date_to": "2026-11-30"},
        "currency": "PLN",
        "income": "3000.00",
        "expense": "100.00",
        "balance": "2900.00",
        "transaction_count": 5,
    }
    assert breakdown["total"] == "100.00"
    assert [(r["category"], r["amount"], r["share_pct"]) for r in breakdown["categories"]] == [
        ("Rozrywka", "70.00", "70.0"),
        ("Transport", "29.70", "29.7"),
        ("Jedzenie", "0.30", "0.3"),
    ]
    assert bad.is_error


async def test_compare_periods(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("200.00", "Jedzenie", "2026-10-05")
    await user.add("100.00", "Transport", "2026-10-06")
    await user.add("250.00", "Jedzenie", "2026-11-05")
    await user.add("40.00", "Rozrywka", "2026-11-06")

    async with client_as(user.id) as c:
        all_cats = await call(
            c,
            "compare_periods",
            period_a_from="2026-10-01",
            period_a_to="2026-10-31",
            period_b_from="2026-11-01",
            period_b_to="2026-11-30",
        )
        food = await call(
            c,
            "compare_periods",
            period_a_from="2026-10-01",
            period_a_to="2026-10-31",
            period_b_from="2026-11-01",
            period_b_to="2026-11-30",
            category="Jedzenie",
        )

    assert all_cats["period_a"]["expense"] == "300.00"
    assert all_cats["period_b"]["expense"] == "290.00"
    assert all_cats["expense_change"] == {"amount": "-10.00", "pct": "-3.3"}
    assert all_cats["income_change"] == {"amount": "0.00", "pct": None}
    rows = {r["category"]: r for r in all_cats["by_category"]}
    assert rows["Transport"]["change"] == {"amount": "-100.00", "pct": "-100.0"}
    assert rows["Rozrywka"]["change"] == {"amount": "40.00", "pct": None}
    assert food["category"] == "Jedzenie" and food["by_category"] == []
    assert food["expense_change"] == {"amount": "50.00", "pct": "25.0"}


async def test_simulate_purchase(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("3000.00", "Wynagrodzenie", "2026-11-01", type=TransactionType.INCOME)
    await user.add("150.00", "Rozrywka", "2026-11-03")
    await user.add("500.00", "Zakupy", "2026-11-04")
    await user.budget("Rozrywka", "200.00")

    async with client_as(user.id) as c:
        with_budget = await call(
            c, "simulate_purchase", amount="80", category="rozrywka", purchase_date="2026-11-20"
        )
        no_budget = await call(
            c, "simulate_purchase", amount="99.99", category="Zakupy", purchase_date="2026-11-20"
        )
        income_cat = await c.call_tool(
            "simulate_purchase",
            {"amount": "10", "category": "Wynagrodzenie"},
            raise_on_error=False,
        )

    assert with_budget["month"] == {"date_from": "2026-11-01", "date_to": "2026-11-30"}
    assert (
        with_budget["category_spent_before"],
        with_budget["category_spent_after"],
        with_budget["budget_remaining_before"],
        with_budget["budget_remaining_after"],
        with_budget["exceeds_budget"],
    ) == ("150.00", "230.00", "50.00", "-30.00", True)
    assert (with_budget["month_balance_before"], with_budget["month_balance_after"]) == (
        "2350.00",
        "2270.00",
    )
    assert no_budget["budget_limit"] is None and no_budget["exceeds_budget"] is None
    assert no_budget["month_balance_after"] == "2250.01"
    assert income_cat.is_error
