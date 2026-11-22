from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Budget, BudgetPeriod, Category, Transaction, TransactionType
from app.repositories.categories import in_scope

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
class ExpenseRow:
    occurred_on: date
    amount: Decimal
    category_id: UUID
    category: str
    main_id: UUID
    main: str
    note: str | None
    recurring: bool


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
        stmt = stmt.where(in_scope(category_id, user_id))
    income, expense, count = (await session.execute(stmt)).one()
    return Totals(income=Decimal(income) + ZERO, expense=Decimal(expense) + ZERO, count=count)


async def breakdown_by_category(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    tx_type: TransactionType,
    parent_id: UUID | None = None,
) -> list[CategoryTotal]:
    total = func.sum(Transaction.amount)
    group = aliased(Category)
    leaf = aliased(Category)
    if parent_id is None:
        on = group.id == func.coalesce(leaf.parent_id, leaf.id)
    else:
        on = group.id == leaf.id
    stmt = (
        select(group.id, group.name, total, func.count(Transaction.id))
        .join(leaf, leaf.id == Transaction.category_id)
        .join(group, on)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == tx_type,
            Transaction.occurred_on >= date_from,
            Transaction.occurred_on <= date_to,
        )
        .group_by(group.id, group.name)
        .order_by(total.desc(), group.name)
    )
    if parent_id is not None:
        stmt = stmt.where(or_(leaf.id == parent_id, leaf.parent_id == parent_id))
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
    scoped = aliased(Category)
    scope = (
        select(scoped.id)
        .where(or_(scoped.id == Budget.category_id, scoped.parent_id == Budget.category_id))
        .correlate(Budget)
    )
    spent = (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == user_id,
            Transaction.category_id.in_(scope),
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


async def expense_rows(
    session: AsyncSession,
    user_id: UUID,
    date_from: date,
    date_to: date,
    category_id: UUID | None = None,
) -> list[ExpenseRow]:
    leaf = aliased(Category)
    main = aliased(Category)
    stmt = (
        select(
            Transaction.occurred_on,
            Transaction.amount,
            leaf.id,
            leaf.name,
            main.id,
            main.name,
            Transaction.note,
            Transaction.recurring_id,
        )
        .join(leaf, leaf.id == Transaction.category_id)
        .join(main, main.id == func.coalesce(leaf.parent_id, leaf.id))
        .where(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.occurred_on >= date_from,
            Transaction.occurred_on <= date_to,
        )
        .order_by(Transaction.occurred_on, Transaction.created_at)
    )
    if category_id is not None:
        stmt = stmt.where(in_scope(category_id, user_id))
    rows = (await session.execute(stmt)).all()
    return [
        ExpenseRow(
            occurred_on=day,
            amount=Decimal(amount) + ZERO,
            category_id=cid,
            category=cname,
            main_id=mid,
            main=mname,
            note=note,
            recurring=rid is not None,
        )
        for day, amount, cid, cname, mid, mname, note, rid in rows
    ]


async def first_transaction_on(session: AsyncSession, user_id: UUID) -> date | None:
    return await session.scalar(
        select(func.min(Transaction.occurred_on)).where(Transaction.user_id == user_id)
    )
