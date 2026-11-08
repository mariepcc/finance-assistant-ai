from typing import Annotated

from app.models import TransactionType
from app.repositories import categories as categories_repo
from pydantic import Field

from finance_tools.context import tool_context
from finance_tools.results import CategoriesResult, CategoryInfo


async def list_categories(
    kind: Annotated[
        TransactionType | None,
        Field(description="expense (wydatki) albo income (przychody); brak = wszystkie"),
    ] = None,
) -> CategoriesResult:
    async with tool_context() as ctx:
        rows = await categories_repo.list_for_user(ctx.session, ctx.user_id, kind)
        return CategoriesResult(categories=[CategoryInfo(name=c.name, kind=c.kind) for c in rows])
