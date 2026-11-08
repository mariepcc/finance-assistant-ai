from datetime import date
from decimal import Decimal
from typing import Annotated

from app.models import TransactionType
from app.repositories import categories as categories_repo
from app.repositories import transactions as tx_repo
from app.repositories.transactions import TransactionFilters
from app.schemas.proposal import ProposedTransaction, TransactionProposalPayload
from app.services import proposals as proposals_service
from pydantic import Field

from finance_tools.context import period, resolve_category, tool_context
from finance_tools.results import (
    ProposedItem,
    SearchResult,
    TransactionItem,
    TransactionProposalResult,
)


async def search_transactions(
    date_from: Annotated[date | None, Field(description="Początek okresu (RRRR-MM-DD)")] = None,
    date_to: Annotated[date | None, Field(description="Koniec okresu (RRRR-MM-DD)")] = None,
    type: Annotated[TransactionType | None, Field(description="expense albo income")] = None,
    category: Annotated[str | None, Field(description="Nazwa kategorii, np. Jedzenie")] = None,
    min_amount: Annotated[Decimal | None, Field(ge=0, description="Minimalna kwota")] = None,
    max_amount: Annotated[Decimal | None, Field(ge=0, description="Maksymalna kwota")] = None,
    text: Annotated[
        str | None, Field(max_length=100, description="Fragment notatki do wyszukania")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Ile transakcji zwrócić")] = 20,
) -> SearchResult:
    if date_from is not None and date_to is not None:
        period(date_from, date_to)
    async with tool_context() as ctx:
        category_id = None
        if category is not None:
            category_id = (await resolve_category(ctx, category, type)).id
        filters = TransactionFilters(
            date_from=date_from,
            date_to=date_to,
            type=type,
            category_id=category_id,
            query=text,
            min_amount=min_amount,
            max_amount=max_amount,
        )
        items, _ = await tx_repo.list_for_user(ctx.session, ctx.user_id, filters, limit)
        totals = await tx_repo.summarize_for_user(ctx.session, ctx.user_id, filters)
        names = {
            c.id: c.name for c in await categories_repo.list_for_user(ctx.session, ctx.user_id)
        }
        return SearchResult(
            currency=ctx.currency,
            matched_count=totals.count,
            matched_income=totals.income,
            matched_expense=totals.expense,
            returned_count=len(items),
            truncated=totals.count > len(items),
            transactions=[
                TransactionItem(
                    occurred_on=t.occurred_on,
                    type=t.type,
                    amount=t.amount,
                    currency=t.currency,
                    category=names.get(t.category_id, "?"),
                    note=t.note,
                )
                for t in items
            ],
        )


async def propose_transaction(
    items: Annotated[
        list[ProposedTransaction],
        Field(
            min_length=1,
            max_length=20,
            description="Transakcje do zapisania; kilka pozycji, gdy użytkownik podał kilka naraz",
        ),
    ],
) -> TransactionProposalResult:
    async with tool_context() as ctx:
        proposal = await proposals_service.propose_transactions(ctx.session, ctx.user_id, items)
        payload = TransactionProposalPayload.model_validate(proposal.payload)
        return TransactionProposalResult(
            proposal_id=proposal.id,
            status="pending",
            expires_at=proposal.expires_at,
            items=[
                ProposedItem(
                    type=i.type,
                    amount=i.amount,
                    currency=i.currency,
                    category=i.category,
                    occurred_on=i.occurred_on,
                    note=i.note,
                )
                for i in payload.items
            ],
        )
