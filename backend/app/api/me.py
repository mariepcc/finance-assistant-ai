from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.auth import CurrentUserDep
from app.repositories import profiles as profiles_repo
from app.schemas.profile import ConsentIn, ProfileOut, ProfileUpdate
from app.services import onboarding

router = APIRouter(prefix="/me", tags=["profil"])


@router.get("", response_model=ProfileOut)
async def get_me(user: CurrentUserDep, session: SessionDep) -> ProfileOut:
    profile = await profiles_repo.get_or_create(session, user.id)
    await session.commit()
    return ProfileOut.model_validate(profile)


@router.patch("", response_model=ProfileOut)
async def update_me(data: ProfileUpdate, user: CurrentUserDep, session: SessionDep) -> ProfileOut:
    profile = await profiles_repo.get_or_create(session, user.id)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return ProfileOut.model_validate(profile)


@router.post("/consent", response_model=ProfileOut)
async def accept_consent(data: ConsentIn, user: CurrentUserDep, session: SessionDep) -> ProfileOut:
    if not data.accepted:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Zgoda jest wymagana")
    profile = await profiles_repo.get_or_create(session, user.id)
    profile = await onboarding.accept_consent(session, profile, data.default_currency)
    await session.commit()
    await session.refresh(profile)
    return ProfileOut.model_validate(profile)
