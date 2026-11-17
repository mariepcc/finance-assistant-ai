from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Transaction, TransactionType


async def list_for_user(
    session: AsyncSession, user_id: UUID, kind: TransactionType | None = None
) -> Sequence[Category]:
    stmt = select(Category).where(Category.user_id == user_id, Category.archived_at.is_(None))
    if kind is not None:
        stmt = stmt.where(Category.kind == kind)
    result = await session.scalars(stmt.order_by(Category.kind, Category.name))
    return result.all()


async def get_for_user(session: AsyncSession, user_id: UUID, category_id: UUID) -> Category | None:
    return await session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )


async def get_by_name(
    session: AsyncSession, user_id: UUID, name: str, kind: TransactionType | None = None
) -> Category | None:
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.archived_at.is_(None),
        func.lower(Category.name) == name.strip().lower(),
    )
    if kind is not None:
        stmt = stmt.where(Category.kind == kind)
    return (await session.scalars(stmt.order_by(Category.kind))).first()


def in_scope(category_id: UUID, user_id: UUID | None = None) -> ColumnElement[bool]:
    scope = select(Category.id).where(
        or_(Category.id == category_id, Category.parent_id == category_id)
    )
    if user_id is not None:
        scope = scope.where(Category.user_id == user_id)
    return Transaction.category_id.in_(scope)


async def scope_ids(session: AsyncSession, user_id: UUID, category_id: UUID) -> list[UUID]:
    rows = await session.scalars(
        select(Category.id).where(
            Category.user_id == user_id,
            or_(Category.id == category_id, Category.parent_id == category_id),
        )
    )
    return list(rows.all())


async def names_by_id(session: AsyncSession, user_id: UUID) -> dict[UUID, tuple[str, str | None]]:
    rows = (
        await session.execute(
            select(Category.id, Category.name, Category.parent_id).where(
                Category.user_id == user_id
            )
        )
    ).all()
    names = {cid: name for cid, name, _ in rows}
    return {
        cid: (names[parent], name) if parent is not None else (name, None)
        for cid, name, parent in rows
    }


async def user_has_any(session: AsyncSession, user_id: UUID) -> bool:
    return bool(await session.scalar(select(exists().where(Category.user_id == user_id))))


async def add_many(session: AsyncSession, categories: list[Category]) -> None:
    session.add_all(categories)
    await session.flush()
