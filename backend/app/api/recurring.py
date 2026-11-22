from datetime import date
from uuid import UUID

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep, SyncRecurring
from app.auth import CurrentUserDep
from app.schemas.recurring import RecurringCreate, RecurringList, RecurringOut, RecurringUpdate
from app.services import recurring as recurring_service

router = APIRouter(prefix="/recurring", tags=["stałe płatności"])


@router.get("", response_model=RecurringList, dependencies=[SyncRecurring])
async def list_recurring(user: CurrentUserDep, session: SessionDep) -> RecurringList:
    rules = await recurring_service.list_for_user(session, user.id)
    totals = recurring_service.monthly_totals(rules)
    return RecurringList(
        items=[RecurringOut.model_validate(r) for r in rules],
        monthly_expense=totals.expense,
        monthly_income=totals.income,
    )


@router.post("", response_model=RecurringOut, status_code=status.HTTP_201_CREATED)
async def create_recurring(
    data: RecurringCreate, user: CurrentUserDep, session: SessionDep
) -> RecurringOut:
    rule = await recurring_service.create(session, user.id, data, date.today())
    await session.commit()
    return RecurringOut.model_validate(rule)


@router.get("/{rule_id}", response_model=RecurringOut)
async def get_recurring(rule_id: UUID, user: CurrentUserDep, session: SessionDep) -> RecurringOut:
    return RecurringOut.model_validate(await recurring_service.get(session, user.id, rule_id))


@router.patch("/{rule_id}", response_model=RecurringOut)
async def update_recurring(
    rule_id: UUID, data: RecurringUpdate, user: CurrentUserDep, session: SessionDep
) -> RecurringOut:
    rule = await recurring_service.update(session, user.id, rule_id, data, date.today())
    await session.commit()
    return RecurringOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recurring(rule_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    await recurring_service.delete(session, user.id, rule_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
