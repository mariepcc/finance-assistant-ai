import calendar
from datetime import date, timedelta
from decimal import Decimal

from app.db import get_sessionmaker
from app.models import RecurringFrequency, RecurringRule, Transaction, TransactionSource

from tests.conftest import ClientAs, MakeUser, UserData, call

TODAY = date.today()
MONTH_START = TODAY.replace(day=1)
MONTH_END = TODAY.replace(day=calendar.monthrange(TODAY.year, TODAY.month)[1])
REMAINING = (MONTH_END - TODAY).days


async def daily_history(user: UserData, category: str, amount: str, days: int) -> None:
    async with get_sessionmaker()() as s:
        for i in range(1, days + 1):
            s.add(
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal(amount),
                    currency="PLN",
                    category_id=user.categories[category],
                    occurred_on=MONTH_START - timedelta(days=i),
                )
            )
        await s.commit()


async def rule(user: UserData, category: str, amount: str, due: date) -> RecurringRule:
    async with get_sessionmaker()() as s:
        r = RecurringRule(
            user_id=user.id,
            type="expense",
            amount=Decimal(amount),
            currency="PLN",
            category_id=user.categories[category],
            name="Netflix",
            frequency=RecurringFrequency.MONTHLY,
            day_of_month=due.day,
            month=None,
            next_due_on=due,
            active=True,
        )
        s.add(r)
        await s.commit()
        return r


async def test_forecast_uses_history_windows_and_planned_payments(
    client_as: ClientAs, make_user: MakeUser
) -> None:
    user = await make_user()
    await daily_history(user, "Spożywcze", "10.00", 90)
    await user.add("20.00", "Spożywcze", MONTH_START.isoformat())
    planned = Decimal("0.00")
    if REMAINING > 0:
        await rule(user, "Streaming", "43.00", MONTH_END)
        planned = Decimal("43.00")
    await user.budget("Jedzenie", "10.00")

    async with client_as(user.id) as c:
        total = await call(c, "forecast_month_end")
        food = await call(c, "forecast_month_end", category="Jedzenie")
        groceries = await call(c, "forecast_month_end", category="Spożywcze")

    variable = Decimal(10 * REMAINING)
    assert total["method"] == "history_windows"
    assert total["history_days"] == 90
    assert total["days_remaining"] == REMAINING
    assert Decimal(total["spent_to_date"]) == Decimal("20.00")
    assert Decimal(total["planned_recurring_expense"]) == planned
    assert Decimal(total["variable_spending_remaining"]["low"]) == variable
    assert Decimal(total["variable_spending_remaining"]["high"]) == variable
    assert Decimal(total["month_end_expense"]["typical"]) == Decimal("20.00") + planned + variable
    assert total["month_end_balance"] is not None

    assert Decimal(food["planned_recurring_expense"]) == Decimal("0.00")
    assert (food["category"], food["budget_limit"], food["likely_exceeds_budget"]) == (
        "Jedzenie",
        "10.00",
        True,
    )
    assert food["month_end_balance"] is None
    assert (groceries["subcategory"], groceries["budget_limit"]) == ("Spożywcze", None)


async def test_forecast_without_history_uses_current_pace(
    client_as: ClientAs, make_user: MakeUser
) -> None:
    user = await make_user()
    await user.add("30.00", "Kawiarnie", MONTH_START.isoformat())

    async with client_as(user.id) as c:
        data = await call(c, "forecast_month_end")

    assert (data["method"], data["history_days"]) == ("current_pace", 0)
    pace = Decimal(data["current_pace_projection"])
    assert Decimal(data["variable_spending_remaining"]["typical"]) == pace


async def test_detect_anomalies_finds_expensive_dinner_only(
    client_as: ClientAs, make_user: MakeUser
) -> None:
    user = await make_user()
    other = await make_user()
    for i, amount in enumerate(("40.00", "45.00", "50.00", "55.00", "60.00"), start=10):
        await user.add(amount, "Restauracje", (MONTH_START - timedelta(days=i)).isoformat())
    for i, amount in enumerate(("5.00", "6.00", "6.00", "7.00", "8.00"), start=10):
        await user.add(amount, "Kawiarnie", (MONTH_START - timedelta(days=i)).isoformat())
    await user.add("486.00", "Restauracje", MONTH_START.isoformat(), note="kolacja urodzinowa")
    await user.add("18.00", "Kawiarnie", MONTH_START.isoformat(), note="kawa")
    recurring = await rule(user, "Restauracje", "900.00", MONTH_END + timedelta(days=1))
    async with get_sessionmaker()() as s:
        s.add(
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("900.00"),
                currency="PLN",
                category_id=user.categories["Restauracje"],
                occurred_on=MONTH_START,
                source=TransactionSource.RECURRING,
                recurring_id=recurring.id,
            )
        )
        await s.commit()
    for i in range(10, 15):
        await other.add("10.00", "Restauracje", (MONTH_START - timedelta(days=i)).isoformat())
    await other.add("999.00", "Restauracje", MONTH_START.isoformat(), note="obce")

    async with client_as(user.id) as c:
        data = await call(c, "detect_anomalies")

    assert [
        (a["amount"], a["note"], a["median_amount"], a["times_median"])
        for a in data["transactions"]
    ] == [("486.00", "kolacja urodzinowa", "50.00", "9.7")]
    assert data["transactions"][0]["subcategory"] == "Restauracje"
    assert data["category_check_done"] is False
    assert "50 zł" in data["rules"]["transaction"]
