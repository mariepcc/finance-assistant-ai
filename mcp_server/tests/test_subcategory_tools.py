from tests.conftest import ClientAs, MakeUser, call

NOV = {"date_from": "2026-11-01", "date_to": "2026-11-30"}


async def test_list_categories_is_a_tree(client_as: ClientAs, make_user: MakeUser) -> None:
    user = await make_user()
    async with client_as(user.id) as c:
        data = await call(c, "list_categories", kind="expense")
    tree = {cat["name"]: cat for cat in data["categories"]}
    assert "Kawiarnie" not in tree
    assert [s["name"] for s in tree["Podróże"]["subcategories"]] == [
        "Atrakcje",
        "Noclegi",
        "Przejazdy",
    ]
    culture = next(s for s in tree["Rozrywka"]["subcategories"] if s["name"] == "Kultura")
    assert culture["description"] == "teatr, muzea, wystawy, opera"
    assert tree["Inne"]["subcategories"] == []


async def test_breakdown_inside_category_and_search_by_parent(
    client_as: ClientAs, make_user: MakeUser
) -> None:
    user = await make_user()
    await user.add("45.00", "Restauracje", "2026-11-03", note="obiad")
    await user.add("14.00", "Kawiarnie", "2026-11-04", note="kawa")
    await user.add("20.00", "Jedzenie", "2026-11-05")
    await user.add("200.00", "Paliwo", "2026-11-06")

    async with client_as(user.id) as c:
        main = await call(c, "get_breakdown_by_category", **NOV)
        food = await call(c, "get_breakdown_by_category", category="Jedzenie", **NOV)
        from_sub = await call(c, "get_breakdown_by_category", category="Kawiarnie", **NOV)
        search = await call(c, "search_transactions", category="Jedzenie")

    assert [(r["category"], r["amount"]) for r in main["categories"]] == [
        ("Transport", "200.00"),
        ("Jedzenie", "79.00"),
    ]
    assert food["parent_category"] == "Jedzenie"
    assert food["total"] == "79.00"
    assert [(r["category"], r["amount"]) for r in food["categories"]] == [
        ("Restauracje", "45.00"),
        ("Jedzenie (bez podkategorii)", "20.00"),
        ("Kawiarnie", "14.00"),
    ]
    assert from_sub["parent_category"] == "Jedzenie"
    assert search["matched_expense"] == "79.00"
    assert {(t["category"], t["subcategory"]) for t in search["transactions"]} == {
        ("Jedzenie", "Restauracje"),
        ("Jedzenie", "Kawiarnie"),
        ("Jedzenie", None),
    }


async def test_simulate_and_propose_with_subcategory(
    client_as: ClientAs, make_user: MakeUser
) -> None:
    user = await make_user()
    await user.budget("Zakupy", "400.00")
    await user.add("150.00", "Ubrania", "2026-11-02")

    async with client_as(user.id) as c:
        sim = await call(
            c,
            "simulate_purchase",
            amount="300.00",
            category="Elektronika",
            purchase_date="2026-11-17",
        )
        proposal = await call(
            c,
            "propose_transaction",
            items=[
                {
                    "type": "expense",
                    "amount": "89.00",
                    "category": "Przejazdy",
                    "occurred_on": "2026-11-17",
                    "note": "pociąg do Krakowa",
                }
            ],
        )
        sub_budget = await c.call_tool(
            "propose_budget", {"category": "Kawiarnie", "amount": "50.00"}, raise_on_error=False
        )

    assert (sim["category"], sim["subcategory"]) == ("Zakupy", "Elektronika")
    assert (sim["category_spent_before"], sim["budget_remaining_after"]) == ("150.00", "-50.00")
    assert sim["exceeds_budget"] is True
    item = proposal["items"][0]
    assert (item["category"], item["subcategory"]) == ("Podróże", "Przejazdy")
    assert sub_budget.is_error
