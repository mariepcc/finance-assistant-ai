from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile


async def get_or_create(session: AsyncSession, user_id: UUID) -> Profile:
    await session.execute(
        insert(Profile).values(id=user_id).on_conflict_do_nothing(index_elements=[Profile.id])
    )
    profile = await session.get(Profile, user_id, populate_existing=True)
    assert profile is not None
    return profile


async def set_consent(session: AsyncSession, profile: Profile, currency: str) -> Profile:
    if profile.gdpr_consent_at is None:
        profile.gdpr_consent_at = datetime.now(UTC)
    profile.default_currency = currency
    await session.flush()
    return profile
