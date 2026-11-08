from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Proposal


async def add(session: AsyncSession, proposal: Proposal) -> Proposal:
    session.add(proposal)
    await session.flush()
    await session.refresh(proposal)
    return proposal


async def get_for_update(
    session: AsyncSession, user_id: UUID, proposal_id: UUID
) -> Proposal | None:
    return await session.scalar(
        select(Proposal)
        .where(Proposal.id == proposal_id, Proposal.user_id == user_id)
        .with_for_update()
    )
