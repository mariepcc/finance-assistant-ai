from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConsentRequiredError, InvalidInputError, NotFoundError
from app.models import Transaction, TransactionSource, TransactionType
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from app.repositories import transactions as tx_repo
from app.schemas.transaction import TransactionCreate, TransactionUpdate


async def _check_category(
    session: AsyncSession, user_id: UUID, category_id: UUID, tx_type: TransactionType
) -> None:
    category = await categories_repo.get_for_user(session, user_id, category_id)
    if category is None or category.archived_at is not None:
        raise InvalidInputError("Nieznana kategoria")
    if category.kind != tx_type:
        raise InvalidInputError("Kategoria nie pasuje do typu transakcji")


async def create(
    session: AsyncSession,
    user_id: UUID,
    data: TransactionCreate,
    source: TransactionSource = TransactionSource.MANUAL,
) -> Transaction:
    profile = await profiles_repo.get_or_create(session, user_id)
    if profile.gdpr_consent_at is None:
        raise ConsentRequiredError("Wymagana zgoda na przetwarzanie danych")
    await _check_category(session, user_id, data.category_id, data.type)
    tx = Transaction(
        user_id=user_id,
        type=data.type,
        amount=data.amount,
        currency=data.currency or profile.default_currency,
        category_id=data.category_id,
        occurred_on=data.occurred_on,
        note=data.note,
        source=source,
    )
    return await tx_repo.add(session, tx)


async def get(session: AsyncSession, user_id: UUID, tx_id: UUID) -> Transaction:
    tx = await tx_repo.get_for_user(session, user_id, tx_id)
    if tx is None:
        raise NotFoundError("Nie znaleziono transakcji")
    return tx


async def update(
    session: AsyncSession, user_id: UUID, tx_id: UUID, data: TransactionUpdate
) -> Transaction:
    tx = await get(session, user_id, tx_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("amount", ...) is None or changes.get("type", ...) is None:
        raise InvalidInputError("Kwota i typ nie mogą być puste")
    for field in ("category_id", "occurred_on"):
        if field in changes and changes[field] is None:
            raise InvalidInputError(f"Pole {field} nie może być puste")
    new_type = changes.get("type", tx.type)
    new_category = changes.get("category_id", tx.category_id)
    if "type" in changes or "category_id" in changes:
        await _check_category(session, user_id, new_category, new_type)
    for field, value in changes.items():
        setattr(tx, field, value)
    await session.flush()
    await session.refresh(tx)
    return tx


async def delete(session: AsyncSession, user_id: UUID, tx_id: UUID) -> None:
    tx = await get(session, user_id, tx_id)
    await tx_repo.delete(session, tx)
