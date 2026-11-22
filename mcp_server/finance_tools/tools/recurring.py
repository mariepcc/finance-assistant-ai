from datetime import date
from decimal import Decimal
from typing import Annotated

from app.models import RecurringFrequency, TransactionType
from app.models.recurring import monthly_equivalent
from app.repositories import categories as categories_repo
from app.schemas.proposal import ProposedRecurring, RecurringProposalPayload
from app.services import proposals as proposals_service
from app.services import recurring as recurring_service
from pydantic import Field

from finance_tools.context import tool_context
from finance_tools.results import RecurringItem, RecurringListResult, RecurringProposalResult


async def list_recurring() -> RecurringListResult:
    async with tool_context() as ctx:
        rules = await recurring_service.list_for_user(ctx.session, ctx.user_id)
        names = await categories_repo.names_by_id(ctx.session, ctx.user_id)
        totals = recurring_service.monthly_totals(rules)
        return RecurringListResult(
            currency=ctx.currency,
            active_count=sum(1 for r in rules if r.active),
            paused_count=sum(1 for r in rules if not r.active),
            monthly_expense_total=totals.expense,
            monthly_income_total=totals.income,
            payments=[
                RecurringItem(
                    name=r.name,
                    type=r.type,
                    amount=r.amount,
                    currency=r.currency,
                    category=names[r.category_id][0],
                    subcategory=names[r.category_id][1],
                    frequency=r.frequency,
                    day_of_month=r.day_of_month,
                    month=r.month,
                    next_payment_on=r.next_due_on,
                    active=r.active,
                    monthly_amount=r.monthly_amount,
                )
                for r in rules
            ],
        )


async def propose_recurring(
    name: Annotated[
        str, Field(min_length=1, max_length=100, description="Nazwa płatności, np. Spotify")
    ],
    amount: Annotated[
        Decimal,
        Field(gt=0, max_digits=12, decimal_places=2, description="Kwota jednej płatności"),
    ],
    category: Annotated[
        str,
        Field(description="Najdokładniejsza pasująca podkategoria z list_categories"),
    ],
    frequency: Annotated[
        RecurringFrequency, Field(description="monthly (co miesiąc) albo yearly (co rok)")
    ],
    day_of_month: Annotated[int, Field(ge=1, le=31, description="Dzień miesiąca płatności")],
    month: Annotated[
        int | None,
        Field(ge=1, le=12, description="Miesiąc płatności, tylko dla yearly"),
    ] = None,
    type: Annotated[
        TransactionType, Field(description="expense (domyślnie) albo income, np. pensja")
    ] = TransactionType.EXPENSE,
) -> RecurringProposalResult:
    item = ProposedRecurring(
        type=type,
        amount=amount,
        category=category,
        name=name,
        frequency=frequency,
        day_of_month=day_of_month,
        month=month,
    )
    async with tool_context() as ctx:
        proposal = await proposals_service.propose_recurring(
            ctx.session, ctx.user_id, item, date.today()
        )
        payload = RecurringProposalPayload.model_validate(proposal.payload)
        return RecurringProposalResult(
            proposal_id=proposal.id,
            status="pending",
            expires_at=proposal.expires_at,
            name=payload.name,
            type=payload.type,
            amount=payload.amount,
            currency=payload.currency,
            category=payload.category,
            subcategory=payload.subcategory,
            frequency=payload.frequency,
            day_of_month=payload.day_of_month,
            month=payload.month,
            first_payment_on=payload.first_payment_on,
            monthly_amount=monthly_equivalent(payload.frequency, payload.amount),
        )
