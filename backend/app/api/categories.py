from fastapi import APIRouter

from app.api.deps import SessionDep
from app.auth import CurrentUserDep
from app.models import TransactionType
from app.repositories import categories as categories_repo
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["kategorie"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    user: CurrentUserDep, session: SessionDep, kind: TransactionType | None = None
) -> list[CategoryOut]:
    rows = await categories_repo.list_for_user(session, user.id, kind)
    return [CategoryOut.model_validate(c) for c in rows]
