from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Profile, TransactionType
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo

DEFAULT_CATEGORIES: list[tuple[str, TransactionType, str, str]] = [
    ("Jedzenie", TransactionType.EXPENSE, "restaurant", "#F97316"),
    ("Transport", TransactionType.EXPENSE, "bus", "#3B82F6"),
    ("Mieszkanie", TransactionType.EXPENSE, "home", "#8B5CF6"),
    ("Rachunki", TransactionType.EXPENSE, "receipt", "#64748B"),
    ("Zdrowie", TransactionType.EXPENSE, "medkit", "#EF4444"),
    ("Rozrywka", TransactionType.EXPENSE, "game-controller", "#EC4899"),
    ("Zakupy", TransactionType.EXPENSE, "bag-handle", "#14B8A6"),
    ("Inne", TransactionType.EXPENSE, "ellipsis-horizontal", "#94A3B8"),
    ("Wynagrodzenie", TransactionType.INCOME, "cash", "#22C55E"),
    ("Inne przychody", TransactionType.INCOME, "add-circle", "#84CC16"),
]


async def accept_consent(session: AsyncSession, profile: Profile, currency: str) -> Profile:
    profile = await profiles_repo.set_consent(session, profile, currency)
    if not await categories_repo.user_has_any(session, profile.id):
        await categories_repo.add_many(
            session,
            [
                Category(
                    user_id=profile.id,
                    name=name,
                    kind=kind,
                    icon=icon,
                    color=color,
                    is_default=True,
                )
                for name, kind, icon, color in DEFAULT_CATEGORIES
            ],
        )
    return profile
