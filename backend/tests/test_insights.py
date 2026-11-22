import uuid
from datetime import date
from decimal import Decimal

from app.repositories.analytics import ExpenseRow
from app.services import insights

D = Decimal
FOOD = uuid.uuid4()
CAFE = uuid.uuid4()
RESTAURANT = uuid.uuid4()


def row(amount: str, leaf: uuid.UUID, name: str, recurring: bool = False) -> ExpenseRow:
    return ExpenseRow(
        occurred_on=date(2026, 11, 10),
        amount=D(amount),
        category_id=leaf,
        category=name,
        main_id=FOOD,
        main="Jedzenie",
        note=None,
        recurring=recurring,
    )


def test_percentile_and_median_interpolate() -> None:
    values = [D("10"), D("20"), D("30"), D("40")]
    assert insights.median(values) == D("25.00")
    assert insights.percentile(values, D("0.1")) == D("13.00")
    assert insights.percentile(values, D("0.9")) == D("37.00")
    assert insights.median([]) == D("0.00")


def test_window_sums_count_missing_days_as_zero() -> None:
    daily = {date(2026, 10, 1): D("10"), date(2026, 10, 3): D("5")}
    sums = insights.window_sums(daily, date(2026, 10, 1), date(2026, 10, 4), 2)
    assert sums == [D("10"), D("5"), D("5")]
    assert insights.window_sums(daily, date(2026, 10, 1), date(2026, 10, 4), 5) == []


def test_variable_range_falls_back_to_pace() -> None:
    windows = [D(str(v)) for v in range(0, 101, 10)]
    rng, method = insights.variable_range(windows, D("80.00"), use_history=True)
    assert (rng.low, rng.typical, rng.high, method) == (
        D("10.00"),
        D("50.00"),
        D("90.00"),
        "history_windows",
    )
    rng, method = insights.variable_range(windows, D("80.00"), use_history=False)
    assert (rng.low, rng.typical, rng.high, method) == (
        D("60.00"),
        D("80.00"),
        D("100.00"),
        "current_pace",
    )


def test_transaction_anomaly_thresholds_and_main_category_fallback() -> None:
    history = [row(str(v), RESTAURANT, "Restauracje") for v in (40, 45, 50, 55, 60)]
    history += [row(str(v), CAFE, "Kawiarnie") for v in (5, 6, 7)]
    period = [
        row("486.00", RESTAURANT, "Restauracje"),
        row("140.00", RESTAURANT, "Restauracje"),
        row("18.00", CAFE, "Kawiarnie"),
        row("200.00", CAFE, "Kawiarnie"),
        row("2200.00", RESTAURANT, "Restauracje", recurring=True),
    ]
    found = insights.transaction_anomalies(period, history)
    assert [(a.amount, a.compared_with, a.median, a.ratio) for a in found] == [
        (D("486.00"), "Restauracje", D("50.00"), D("9.7")),
        (D("200.00"), "Jedzenie", D("42.50"), D("4.7")),
    ]


def test_category_anomalies_scale_partial_month() -> None:
    history = [{"Zakupy": D("300")}, {"Zakupy": D("400")}, {"Zakupy": D("350")}]
    full = insights.category_anomalies({"Zakupy": D("600.00")}, history, D("1"))
    assert [(a.expected, a.ratio) for a in full] == [(D("350.00"), D("1.7"))]
    assert insights.category_anomalies({"Zakupy": D("450.00")}, history, D("1")) == []
    half = insights.category_anomalies({"Zakupy": D("300.00")}, history, D("0.5"))
    assert [(a.expected, a.median_month) for a in half] == [(D("175.00"), D("350.00"))]


def test_months_before_crosses_year() -> None:
    assert insights.months_before(date(2026, 2, 1), 3) == [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
    ]
