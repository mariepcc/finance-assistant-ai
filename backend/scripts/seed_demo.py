import argparse
import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.models import Budget, Category, Transaction, TransactionType
from app.repositories import profiles as profiles_repo
from app.services import onboarding

MONTHS_BACK = 3
SEED = 2026

RECURRING: list[tuple[int, str, str, TransactionType, str | None]] = [
    (1, "Wynagrodzenie", "6500.00", TransactionType.INCOME, "pensja"),
    (2, "Mieszkanie", "2200.00", TransactionType.EXPENSE, "czynsz"),
    (5, "Rachunki", "89.99", TransactionType.EXPENSE, "internet"),
    (12, "Rozrywka", "23.99", TransactionType.EXPENSE, "Spotify"),
    (15, "Rachunki", "164.30", TransactionType.EXPENSE, "prąd"),
]

RANDOM_SPENDING: list[tuple[str, tuple[str | None, ...], float, float, float]] = [
    ("Jedzenie", ("Biedronka", "Lidl", "Żabka", "kawa", "obiad", None), 0.9, 8, 180),
    ("Transport", ("bilet", "Bolt", "paliwo", None), 0.45, 4.4, 160),
    ("Rozrywka", ("kino", "koncert", "książka", None), 0.12, 25, 220),
    ("Zakupy", ("ubrania", "Rossmann", "Allegro", None), 0.15, 20, 350),
    ("Zdrowie", ("apteka", "dentysta", None), 0.05, 15, 300),
    ("Inne", (None,), 0.04, 10, 120),
]

BUDGETS = {"Jedzenie": "1200.00", "Transport": "250.00", "Rozrywka": "300.00", "Zakupy": "400.00"}


def month_start(day: date, back: int) -> date:
    month = day.month - back
    year = day.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def build_transactions(
    user_id: UUID, categories: dict[str, UUID], today: date
) -> list[Transaction]:
    rng = random.Random(SEED)
    start = month_start(today, MONTHS_BACK - 1)
    result: list[Transaction] = []

    def add(
        day: date, category: str, amount: Decimal, kind: TransactionType, note: str | None
    ) -> None:
        result.append(
            Transaction(
                user_id=user_id,
                type=kind,
                amount=amount,
                currency="PLN",
                category_id=categories[category],
                occurred_on=day,
                note=note,
            )
        )

    day = start
    while day <= today:
        for dom, category, fixed, kind, note in RECURRING:
            if day.day == dom:
                add(day, category, Decimal(fixed), kind, note)
        for category, notes, chance, low, high in RANDOM_SPENDING:
            if rng.random() < chance:
                amount = Decimal(str(round(rng.uniform(low, high), 2)))
                add(day, category, amount, TransactionType.EXPENSE, rng.choice(notes))
        day += timedelta(days=1)
    return result


async def find_user(session: AsyncSession, email: str) -> UUID:
    user_id = await session.scalar(
        text("select id from auth.users where lower(email) = lower(:email)"), {"email": email}
    )
    if user_id is None:
        raise SystemExit(f"Nie znaleziono użytkownika {email} w auth.users (Supabase).")
    return UUID(str(user_id))


async def main(email: str, reset: bool) -> None:
    async with get_sessionmaker()() as session:
        user_id = await find_user(session, email)
        profile = await profiles_repo.get_or_create(session, user_id)
        await onboarding.accept_consent(session, profile, profile.default_currency)
        existing = await session.scalar(select(func.count()).where(Transaction.user_id == user_id))
        if existing and not reset:
            raise SystemExit(
                f"Konto ma już {existing} transakcji. Uruchom z --reset, aby je usunąć "
                "i wstawić dane przykładowe."
            )
        await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        await session.execute(delete(Budget).where(Budget.user_id == user_id))
        rows = (await session.scalars(select(Category).where(Category.user_id == user_id))).all()
        categories = {c.name: c.id for c in rows}
        transactions = build_transactions(user_id, categories, date.today())
        session.add_all(transactions)
        session.add_all(
            Budget(user_id=user_id, category_id=categories[name], amount=Decimal(amount))
            for name, amount in BUDGETS.items()
        )
        await session.commit()
    print(f"{email}: {len(transactions)} transakcji, {len(BUDGETS)} budżety.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dane przykładowe dla konta testowego")
    parser.add_argument("--email", required=True)
    parser.add_argument("--reset", action="store_true", help="usuń transakcje i budżety konta")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.reset))
