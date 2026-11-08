from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import SessionDep
from app.auth import CurrentUserDep
from app.models import TransactionType
from app.repositories import transactions as tx_repo
from app.schemas.transaction import (
    TransactionCreate,
    TransactionOut,
    TransactionPage,
    TransactionUpdate,
)
from app.services import transactions as tx_service

router = APIRouter(prefix="/transactions", tags=["transakcje"])


@router.get("", response_model=TransactionPage)
async def list_transactions(
    user: CurrentUserDep,
    session: SessionDep,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    type: TransactionType | None = None,
    category_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> TransactionPage:
    filters = tx_repo.TransactionFilters(
        date_from=date_from, date_to=date_to, type=type, category_id=category_id, query=q
    )
    try:
        items, next_cursor = await tx_repo.list_for_user(session, user.id, filters, limit, cursor)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nieprawidłowy kursor") from exc
    return TransactionPage(
        items=[TransactionOut.model_validate(t) for t in items], next_cursor=next_cursor
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate, user: CurrentUserDep, session: SessionDep
) -> TransactionOut:
    tx = await tx_service.create(session, user.id, data)
    await session.commit()
    return TransactionOut.model_validate(tx)


@router.get("/{tx_id}", response_model=TransactionOut)
async def get_transaction(tx_id: UUID, user: CurrentUserDep, session: SessionDep) -> TransactionOut:
    return TransactionOut.model_validate(await tx_service.get(session, user.id, tx_id))


@router.patch("/{tx_id}", response_model=TransactionOut)
async def update_transaction(
    tx_id: UUID, data: TransactionUpdate, user: CurrentUserDep, session: SessionDep
) -> TransactionOut:
    tx = await tx_service.update(session, user.id, tx_id, data)
    await session.commit()
    return TransactionOut.model_validate(tx)


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(tx_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    await tx_service.delete(session, user.id, tx_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
