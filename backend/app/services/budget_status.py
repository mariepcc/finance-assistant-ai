from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

BudgetState = Literal["ok", "warning", "exceeded"]

WARNING_PCT = Decimal("80")


def used_pct(spent: Decimal, limit: Decimal) -> Decimal:
    if limit == 0:
        return Decimal("0.0")
    return (spent / limit * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def budget_state(spent: Decimal, limit: Decimal) -> BudgetState:
    if spent > limit:
        return "exceeded"
    if used_pct(spent, limit) >= WARNING_PCT:
        return "warning"
    return "ok"
