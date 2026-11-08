from enum import StrEnum


class TransactionType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class TransactionSource(StrEnum):
    MANUAL = "manual"
    ASSISTANT = "assistant"


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"


class ProposalKind(StrEnum):
    TRANSACTION = "transaction"
    BUDGET = "budget"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
