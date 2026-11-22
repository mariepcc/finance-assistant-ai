from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import SessionDep, SyncRecurring
from app.auth import CurrentUserDep
from app.schemas.budget import BudgetIn, BudgetsOut, BudgetSuggestion
from app.schemas.proposal import BudgetOut
from app.services import budgets as budgets_service

router = APIRouter(prefix="/budgets", tags=["budżety"])


@router.get("", response_model=BudgetsOut, dependencies=[SyncRecurring])
async def list_budgets(
    user: CurrentUserDep,
    session: SessionDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> BudgetsOut:
    return await budgets_service.overview(session, user.id, month, date.today())


@router.get("/suggestions", response_model=list[BudgetSuggestion])
async def budget_suggestions(user: CurrentUserDep, session: SessionDep) -> list[BudgetSuggestion]:
    return await budgets_service.suggestions(session, user.id, date.today())


@router.put("/{category_id}", response_model=BudgetOut)
async def save_budget(
    category_id: UUID, data: BudgetIn, user: CurrentUserDep, session: SessionDep
) -> BudgetOut:
    budget = await budgets_service.save(session, user.id, category_id, data.amount)
    await session.commit()
    return BudgetOut.model_validate(budget)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(category_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    await budgets_service.remove(session, user.id, category_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
