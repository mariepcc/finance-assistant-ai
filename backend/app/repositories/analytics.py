from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, BudgetPeriod, Category, Transaction, TransactionType

ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class Totals:
    income: Decimal
    expense: Decimal
    count: int

    @property
    def balance(self) -> Decimal:
        return self.income - self.expense


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    category_id: UUID
    name: str
    total: Decimal
    count: int


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    budget: Budget
    category_name: str
    spent: Decimal


def _sum_of(tx_type: TransactionType) -> ColumnElement[Decimal]:
    return func.coalesce(
        func.sum(case((Transaction.type == tx_type, Transaction.amount), else_=0)), 0
    )


async def totals(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    category_id: UUID | None = None,
) -> Totals:
    stmt = select(
        _sum_of(TransactionType.INCOME),
        _sum_of(TransactionType.EXPENSE),
        func.count(Transaction.id),
    ).where(
        Transaction.user_id == user_id,
        Transaction.occurred_on >= date_from,
        Transaction.occurred_on <= date_to,
    )
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    income, expense, count = (await session.execute(stmt)).one()
    return Totals(income=Decimal(income) + ZERO, expense=Decimal(expense) + ZERO, count=count)


async def breakdown_by_category(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    tx_type: TransactionType,
) -> list[CategoryTotal]:
    total = func.sum(Transaction.amount)
    stmt = (
        select(Category.id, Category.name, total, func.count(Transaction.id))
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == tx_type,
            Transaction.occurred_on >= date_from,
            Transaction.occurred_on <= date_to,
        )
        .group_by(Category.id, Category.name)
        .order_by(total.desc(), Category.name)
    )
    rows = (await session.execute(stmt)).all()
    return [
        CategoryTotal(category_id=cid, name=name, total=Decimal(amount) + ZERO, count=count)
        for cid, name, amount, count in rows
    ]


async def budget_for_category(
    session: AsyncSession, user_id: UUID, category_id: UUID
) -> Budget | None:
    return await session.scalar(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.period == BudgetPeriod.MONTHLY,
        )
    )


async def budget_usage(
    session: AsyncSession, user_id: UUID, month_start: date, month_end: date
) -> list[BudgetUsage]:
    spent = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == user_id,
            Transaction.category_id == Budget.category_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.occurred_on >= month_start,
            Transaction.occurred_on <= month_end,
        )
        .scalar_subquery()
    )
    stmt = (
        select(Budget, Category.name, spent)
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == user_id, Budget.period == BudgetPeriod.MONTHLY)
        .order_by(Category.name)
    )
    rows = (await session.execute(stmt)).all()
    return [
        BudgetUsage(budget=b, category_name=name, spent=Decimal(s) + ZERO) for b, name, s in rows
    ]
