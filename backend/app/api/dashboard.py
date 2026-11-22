from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep, SyncRecurring
from app.auth import CurrentUserDep
from app.schemas.dashboard import Dashboard
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["pulpit"])


@router.get("", response_model=Dashboard, dependencies=[SyncRecurring])
async def get_dashboard(
    user: CurrentUserDep,
    session: SessionDep,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> Dashboard:
    return await dashboard_service.build(session, user.id, month, date.today())
