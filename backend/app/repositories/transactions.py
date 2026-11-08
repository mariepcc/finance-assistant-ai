import base64
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, case, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionType


@dataclass(frozen=True, slots=True)
class TransactionFilters:
    date_from: date | None = None
    date_to: date | None = None
    type: TransactionType | None = None
    category_id: UUID | None = None
    query: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None


def encode_cursor(tx: Transaction) -> str:
    raw = f"{tx.occurred_on.isoformat()}|{tx.created_at.isoformat()}|{tx.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[date, datetime, UUID]:
    occurred_on, created_at, tx_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
    return date.fromisoformat(occurred_on), datetime.fromisoformat(created_at), UUID(tx_id)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters[S: Select[*tuple[Any, ...]]](stmt: S, f: TransactionFilters) -> S:
    if f.date_from is not None:
        stmt = stmt.where(Transaction.occurred_on >= f.date_from)
    if f.date_to is not None:
        stmt = stmt.where(Transaction.occurred_on <= f.date_to)
    if f.type is not None:
        stmt = stmt.where(Transaction.type == f.type)
    if f.category_id is not None:
        stmt = stmt.where(Transaction.category_id == f.category_id)
    if f.min_amount is not None:
        stmt = stmt.where(Transaction.amount >= f.min_amount)
    if f.max_amount is not None:
        stmt = stmt.where(Transaction.amount <= f.max_amount)
    if f.query:
        stmt = stmt.where(Transaction.note.ilike(f"%{_escape_like(f.query)}%", escape="\\"))
    return stmt


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    filters: TransactionFilters,
    limit: int,
    cursor: str | None = None,
) -> tuple[Sequence[Transaction], str | None]:
    stmt = _apply_filters(select(Transaction).where(Transaction.user_id == user_id), filters)
    order_key = tuple_(Transaction.occurred_on, Transaction.created_at, Transaction.id)
    if cursor is not None:
        stmt = stmt.where(order_key < tuple_(*decode_cursor(cursor)))
    stmt = stmt.order_by(
        Transaction.occurred_on.desc(), Transaction.created_at.desc(), Transaction.id.desc()
    ).limit(limit + 1)
    rows = (await session.scalars(stmt)).all()
    has_more = len(rows) > limit
    items = rows[:limit]
    return items, (encode_cursor(items[-1]) if has_more else None)


@dataclass(frozen=True, slots=True)
class FilteredTotals:
    count: int
    income: Decimal
    expense: Decimal


async def summarize_for_user(
    session: AsyncSession, user_id: UUID, filters: TransactionFilters
) -> FilteredTotals:
    def total(tx_type: TransactionType) -> ColumnElement[Decimal]:
        return func.coalesce(
            func.sum(case((Transaction.type == tx_type, Transaction.amount), else_=0)), 0
        )

    stmt = select(
        func.count(Transaction.id),
        total(TransactionType.INCOME),
        total(TransactionType.EXPENSE),
    ).where(Transaction.user_id == user_id)
    stmt = _apply_filters(stmt, filters)
    count, income, expense = (await session.execute(stmt)).one()
    return FilteredTotals(
        count=count,
        income=Decimal(income) + Decimal("0.00"),
        expense=Decimal(expense) + Decimal("0.00"),
    )


async def get_for_user(session: AsyncSession, user_id: UUID, tx_id: UUID) -> Transaction | None:
    return await session.scalar(
        select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )


async def add(session: AsyncSession, tx: Transaction) -> Transaction:
    session.add(tx)
    await session.flush()
    await session.refresh(tx)
    return tx


async def delete(session: AsyncSession, tx: Transaction) -> None:
    await session.delete(tx)
    await session.flush()
