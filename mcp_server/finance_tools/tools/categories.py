from typing import Annotated

from app.models import TransactionType
from app.repositories import categories as categories_repo
from pydantic import Field

from finance_tools.context import tool_context
from finance_tools.results import CategoriesResult, CategoryInfo, SubcategoryInfo


async def list_categories(
    kind: Annotated[
        TransactionType | None,
        Field(description="expense (wydatki) albo income (przychody); brak = wszystkie"),
    ] = None,
) -> CategoriesResult:
    async with tool_context() as ctx:
        rows = await categories_repo.list_for_user(ctx.session, ctx.user_id, kind)
        children: dict[object, list[SubcategoryInfo]] = {}
        for c in rows:
            if c.parent_id is not None:
                children.setdefault(c.parent_id, []).append(
                    SubcategoryInfo(name=c.name, description=c.description)
                )
        return CategoriesResult(
            categories=[
                CategoryInfo(
                    name=c.name,
                    kind=c.kind,
                    description=c.description,
                    subcategories=children.get(c.id, []),
                )
                for c in rows
                if c.parent_id is None
            ]
        )
