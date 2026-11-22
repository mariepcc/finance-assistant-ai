from datetime import date
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUserDep
from app.db import get_session
from app.services import recurring as recurring_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def sync_recurring(user: CurrentUserDep, session: SessionDep) -> None:
    if await recurring_service.materialize_due(session, user.id, date.today()):
        await session.commit()


SyncRecurring = Depends(sync_recurring)
