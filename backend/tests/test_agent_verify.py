from datetime import date
from decimal import Decimal

from app.agent.verify import allowed_numbers, numbers_in_text, unverified_numbers
from tests.fakes import BUDGETS, SUMMARY

TODAY = date(2026, 11, 9)


def allowed(*sources: object, user: tuple[str, ...] = ()) -> set[Decimal]:
    return allowed_numbers(list(sources), user, TODAY)


def test_polish_number_formats() -> None:
    found = [v for _, v in numbers_in_text("Wydałaś 2 520,16 zł (31,7%), a w sumie 7 937,79 zł.")]
    assert found == [Decimal("2520.16"), Decimal("31.7"), Decimal("7937.79")]


def test_dot_decimal_and_sentence_end() -> None:
    found = [v for _, v in numbers_in_text("Saldo: 642.65. Koniec 2026.")]
    assert found == [Decimal("642.65"), Decimal("2026")]


def test_numbers_from_tool_results_pass() -> None:
    text = (
        "W październiku wydałaś 7937,79 zł przy przychodach 6500 zł, "
        "saldo -1437,79 zł (57 transakcji)."
    )
    assert unverified_numbers(text, allowed(SUMMARY)) == []


def test_rounded_or_invented_numbers_fail() -> None:
    text = "Wydałaś około 7938 zł, czyli 122% przychodów."
    assert unverified_numbers(text, allowed(SUMMARY)) == ["7938", "122"]


def test_small_integers_and_dates_are_allowed() -> None:
    text = "Od 1 do 31 października 2026 masz 3 przekroczone limity."
    assert unverified_numbers(text, allowed(SUMMARY)) == []


def test_numbers_from_user_message_are_allowed() -> None:
    text = "Przygotowałam wydatek 4,40 zł na bilet i 14 zł na kawę."
    assert unverified_numbers(text, allowed(user=("Kawa 14 zł i bilet 4,40",))) == []


def test_nested_results_and_negative_values() -> None:
    text = "Transport: limit 250,00 zł, wydano 449,71 zł, przekroczenie o 199,71 zł."
    assert unverified_numbers(text, allowed(BUDGETS)) == ["199,71"]
    with_remaining = {**BUDGETS, "remaining": "-199.71"}
    assert unverified_numbers(text, allowed(with_remaining)) == []
