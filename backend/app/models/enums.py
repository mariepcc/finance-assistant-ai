from enum import StrEnum


class TransactionType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"


class TransactionSource(StrEnum):
    MANUAL = "manual"
    ASSISTANT = "assistant"
    RECURRING = "recurring"


class BudgetPeriod(StrEnum):
    MONTHLY = "monthly"


class RecurringFrequency(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class ProposalKind(StrEnum):
    TRANSACTION = "transaction"
    BUDGET = "budget"
    RECURRING = "recurring"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"
