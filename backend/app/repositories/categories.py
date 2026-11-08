from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, TransactionType


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


async def user_has_any(session: AsyncSession, user_id: UUID) -> bool:
    return bool(await session.scalar(select(exists().where(Category.user_id == user_id))))


async def add_many(session: AsyncSession, categories: list[Category]) -> None:
    session.add_all(categories)
    await session.flush()
