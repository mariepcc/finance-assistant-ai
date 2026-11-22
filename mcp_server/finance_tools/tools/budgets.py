from decimal import Decimal
from typing import Annotated

from app.repositories import analytics
from app.schemas.proposal import BudgetProposalPayload
from app.services import proposals as proposals_service
from app.services.budget_status import budget_state, used_pct
from pydantic import Field

from finance_tools.context import parse_month, tool_context
from finance_tools.results import (
    BudgetLine,
    BudgetProposalResult,
    BudgetStatusResult,
)


async def get_budget_status(
    month: Annotated[
        str | None,
        Field(description="Miesiąc RRRR-MM; domyślnie bieżący", pattern=r"^\d{4}-\d{2}$"),
    ] = None,
) -> BudgetStatusResult:
    m = parse_month(month)
    async with tool_context() as ctx:
        usage = await analytics.budget_usage(ctx.session, ctx.user_id, m.date_from, m.date_to)
        lines = []
        for u in usage:
            used = used_pct(u.spent, u.budget.amount)
            lines.append(
                BudgetLine(
                    category=u.category_name,
                    limit=u.budget.amount,
                    spent=u.spent,
                    remaining=u.budget.amount - u.spent,
                    used_pct=used,
                    status=budget_state(u.spent, u.budget.amount),
                )
            )
        return BudgetStatusResult(
            month=m,
            currency=ctx.currency,
            total_limit=sum((u.budget.amount for u in usage), Decimal("0.00")),
            total_spent=sum((u.spent for u in usage), Decimal("0.00")),
            budgets=lines,
        )


async def propose_budget(
    category: Annotated[str, Field(description="Kategoria wydatków, np. Jedzenie")],
    amount: Annotated[
        Decimal, Field(gt=0, max_digits=12, decimal_places=2, description="Miesięczny limit")
    ],
) -> BudgetProposalResult:
    async with tool_context() as ctx:
        proposal = await proposals_service.propose_budget(
            ctx.session, ctx.user_id, category, amount
        )
        payload = BudgetProposalPayload.model_validate(proposal.payload)
        return BudgetProposalResult(
            proposal_id=proposal.id,
            status="pending",
            expires_at=proposal.expires_at,
            category=payload.category,
            currency=payload.currency,
            amount=payload.amount,
            previous_amount=payload.previous_amount,
        )
