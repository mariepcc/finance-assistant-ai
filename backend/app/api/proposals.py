from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth import CurrentUserDep
from app.errors import GoneError
from app.schemas.proposal import BudgetOut, ConfirmOut, ProposalOut
from app.schemas.transaction import TransactionOut
from app.services import proposals as proposals_service

router = APIRouter(prefix="/proposals", tags=["propozycje"])


@router.post("/{proposal_id}/confirm", response_model=ConfirmOut)
async def confirm_proposal(
    proposal_id: UUID, user: CurrentUserDep, session: SessionDep
) -> ConfirmOut:
    try:
        result = await proposals_service.confirm(session, user.id, proposal_id)
    except GoneError:
        await session.commit()
        raise
    await session.commit()
    return ConfirmOut(
        proposal=ProposalOut.model_validate(result.proposal),
        transactions=[TransactionOut.model_validate(t) for t in result.transactions],
        budget=BudgetOut.model_validate(result.budget) if result.budget else None,
    )


@router.post("/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    proposal_id: UUID, user: CurrentUserDep, session: SessionDep
) -> ProposalOut:
    try:
        proposal = await proposals_service.reject(session, user.id, proposal_id)
    except GoneError:
        await session.commit()
        raise
    await session.commit()
    return ProposalOut.model_validate(proposal)
