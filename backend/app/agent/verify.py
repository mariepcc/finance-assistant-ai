import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

NUMBER = re.compile(r"(?<![\w,.])(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)?")
SMALL_INT_LIMIT = 31


def _to_decimal(raw: str) -> Decimal | None:
    cleaned = re.sub(r"[   ]", "", raw).replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def numbers_in_text(text: str) -> list[tuple[str, Decimal]]:
    found: list[tuple[str, Decimal]] = []
    for match in NUMBER.finditer(text):
        value = _to_decimal(match.group())
        if value is not None:
            found.append((match.group(), value))
    return found


def numbers_in_data(data: Any) -> set[Decimal]:
    found: set[Decimal] = set()
    if isinstance(data, bool) or data is None:
        return found
    if isinstance(data, int | float | Decimal):
        found.add(abs(Decimal(str(data))))
    elif isinstance(data, str):
        found.update(v for _, v in numbers_in_text(data))
    elif isinstance(data, dict):
        for value in data.values():
            found |= numbers_in_data(value)
    elif isinstance(data, list | tuple):
        for item in data:
            found |= numbers_in_data(item)
    return found


def allowed_numbers(sources: Iterable[Any], user_texts: Iterable[str], today: date) -> set[Decimal]:
    allowed: set[Decimal] = set()
    for source in sources:
        allowed |= numbers_in_data(source)
    for text in user_texts:
        allowed |= numbers_in_data(text)
    allowed |= numbers_in_data(today.isoformat())
    return allowed


def is_small_int(value: Decimal) -> bool:
    return value == value.to_integral_value() and 0 <= value <= SMALL_INT_LIMIT


def unverified_numbers(answer: str, allowed: set[Decimal]) -> list[str]:
    return [
        raw
        for raw, value in numbers_in_text(answer)
        if value not in allowed and not is_small_int(value)
    ]
