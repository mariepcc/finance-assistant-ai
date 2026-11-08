import calendar
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.db import get_sessionmaker
from app.errors import DomainError
from app.models import Category, TransactionType
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from fastmcp.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from finance_tools.auth import current_user_id
from finance_tools.results import Period


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: AsyncSession
    user_id: UUID
    currency: str


@asynccontextmanager
async def tool_context() -> AsyncIterator[ToolContext]:
    user_id = current_user_id()
    async with get_sessionmaker()() as session:
        try:
            profile = await profiles_repo.get_or_create(session, user_id)
            yield ToolContext(session=session, user_id=user_id, currency=profile.default_currency)
            await session.commit()
        except DomainError as exc:
            await session.rollback()
            raise ToolError(exc.message) from exc


async def resolve_category(
    ctx: ToolContext, name: str, kind: TransactionType | None = None
) -> Category:
    category = await categories_repo.get_by_name(ctx.session, ctx.user_id, name, kind)
    if category is None:
        available = await categories_repo.list_for_user(ctx.session, ctx.user_id, kind)
        names = ", ".join(c.name for c in available)
        raise ToolError(f"Nieznana kategoria „{name}”. Dostępne: {names}")
    return category


def period(date_from: date, date_to: date) -> Period:
    if date_from > date_to:
        raise ToolError("Data początkowa nie może być późniejsza niż końcowa")
    return Period(date_from=date_from, date_to=date_to)


def month_of(day: date) -> Period:
    last = calendar.monthrange(day.year, day.month)[1]
    return Period(date_from=day.replace(day=1), date_to=day.replace(day=last))


def parse_month(value: str | None) -> Period:
    if value is None:
        return month_of(date.today())
    try:
        year, month = (int(part) for part in value.split("-"))
        return month_of(date(year, month, 1))
    except ValueError as exc:
        raise ToolError("Miesiąc w formacie RRRR-MM, np. 2026-11") from exc
