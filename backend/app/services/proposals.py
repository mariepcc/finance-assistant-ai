from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import (
    ConflictError,
    ConsentRequiredError,
    GoneError,
    InvalidInputError,
    NotFoundError,
)
from app.models import (
    Budget,
    BudgetPeriod,
    Category,
    Profile,
    Proposal,
    ProposalKind,
    ProposalStatus,
    RecurringRule,
    Transaction,
    TransactionSource,
    TransactionType,
)
from app.repositories import analytics as analytics_repo
from app.repositories import categories as categories_repo
from app.repositories import profiles as profiles_repo
from app.repositories import proposals as proposals_repo
from app.repositories import transactions as tx_repo
from app.schemas.proposal import (
    BudgetProposalPayload,
    ConfirmIn,
    EditedRecurring,
    EditedTransaction,
    ProposedRecurring,
    ProposedTransaction,
    RecurringDraft,
    RecurringProposalPayload,
    TransactionProposalItem,
    TransactionProposalPayload,
)
from app.schemas.recurring import RecurringCreate
from app.services import recurring as recurring_service

PROPOSAL_TTL = timedelta(minutes=15)
MAX_ITEMS = 20


@dataclass
class ConfirmResult:
    proposal: Proposal
    transactions: list[Transaction] = field(default_factory=list)
    budget: Budget | None = None
    recurring: RecurringRule | None = None


async def _consented_profile(session: AsyncSession, user_id: UUID) -> Profile:
    profile = await profiles_repo.get_or_create(session, user_id)
    if profile.gdpr_consent_at is None:
        raise ConsentRequiredError("Wymagana zgoda na przetwarzanie danych")
    return profile


async def resolve_category(
    session: AsyncSession, user_id: UUID, name: str, kind: TransactionType
) -> Category:
    category = await categories_repo.get_by_name(session, user_id, name, kind)
    if category is None:
        available = await categories_repo.list_for_user(session, user_id, kind)
        names = ", ".join(c.name for c in available)
        raise InvalidInputError(f"Nieznana kategoria „{name}”. Dostępne: {names}")
    return category


async def category_labels(
    session: AsyncSession, user_id: UUID, category: Category
) -> dict[str, str | None]:
    if category.parent_id is None:
        return {"category": category.name, "subcategory": None}
    parent = await categories_repo.get_for_user(session, user_id, category.parent_id)
    assert parent is not None
    return {"category": parent.name, "subcategory": category.name}


async def propose_transactions(
    session: AsyncSession, user_id: UUID, items: list[ProposedTransaction]
) -> Proposal:
    if not 1 <= len(items) <= MAX_ITEMS:
        raise InvalidInputError(f"Propozycja musi mieć od 1 do {MAX_ITEMS} transakcji")
    profile = await _consented_profile(session, user_id)
    resolved = []
    for item in items:
        category = await resolve_category(session, user_id, item.category, item.type)
        resolved.append(
            TransactionProposalItem(
                type=item.type,
                amount=item.amount,
                currency=profile.default_currency,
                category_id=category.id,
                **await category_labels(session, user_id, category),
                occurred_on=item.occurred_on,
                note=item.note,
            )
        )
    payload = TransactionProposalPayload(items=resolved)
    return await proposals_repo.add(
        session,
        Proposal(
            user_id=user_id,
            kind=ProposalKind.TRANSACTION,
            payload=payload.model_dump(mode="json"),
            expires_at=datetime.now(UTC) + PROPOSAL_TTL,
        ),
    )


async def propose_budget(
    session: AsyncSession, user_id: UUID, category_name: str, amount: Decimal
) -> Proposal:
    profile = await _consented_profile(session, user_id)
    category = await resolve_category(session, user_id, category_name, TransactionType.EXPENSE)
    if category.parent_id is not None:
        labels = await category_labels(session, user_id, category)
        raise InvalidInputError(
            f"Budżet ustawiasz dla kategorii głównej („{labels['category']}”), "
            f"nie dla podkategorii „{category.name}”"
        )
    existing = await analytics_repo.budget_for_category(session, user_id, category.id)
    payload = BudgetProposalPayload(
        category_id=category.id,
        category=category.name,
        amount=amount,
        currency=profile.default_currency,
        previous_amount=existing.amount if existing else None,
    )
    return await proposals_repo.add(
        session,
        Proposal(
            user_id=user_id,
            kind=ProposalKind.BUDGET,
            payload=payload.model_dump(mode="json"),
            expires_at=datetime.now(UTC) + PROPOSAL_TTL,
        ),
    )


async def propose_recurring(
    session: AsyncSession, user_id: UUID, item: ProposedRecurring, today: date
) -> Proposal:
    profile = await _consented_profile(session, user_id)
    category = await resolve_category(session, user_id, item.category, item.type)
    payload = RecurringProposalPayload(
        type=item.type,
        amount=item.amount,
        currency=profile.default_currency,
        category_id=category.id,
        **await category_labels(session, user_id, category),
        name=item.name.strip(),
        frequency=item.frequency,
        day_of_month=item.day_of_month,
        month=item.month,
        first_payment_on=recurring_service.first_due(item, today),
    )
    return await proposals_repo.add(
        session,
        Proposal(
            user_id=user_id,
            kind=ProposalKind.RECURRING,
            payload=payload.model_dump(mode="json"),
            expires_at=datetime.now(UTC) + PROPOSAL_TTL,
        ),
    )


async def _pending(session: AsyncSession, user_id: UUID, proposal_id: UUID) -> Proposal:
    proposal = await proposals_repo.get_for_update(session, user_id, proposal_id)
    if proposal is None:
        raise NotFoundError("Nie znaleziono propozycji")
    if proposal.status != ProposalStatus.PENDING:
        raise ConflictError("Propozycja została już rozpatrzona")
    if proposal.expires_at <= datetime.now(UTC):
        proposal.status = ProposalStatus.EXPIRED
        await session.flush()
        raise GoneError("Propozycja wygasła")
    return proposal


async def _apply_item_edits(
    session: AsyncSession,
    user_id: UUID,
    payload: TransactionProposalPayload,
    edited: list[EditedTransaction],
) -> TransactionProposalPayload:
    currency = payload.items[0].currency
    items = []
    for item in edited:
        category = await categories_repo.get_for_user(session, user_id, item.category_id)
        if category is None or category.archived_at is not None or category.kind != item.type:
            raise InvalidInputError("Wybrana kategoria nie pasuje do typu transakcji")
        items.append(
            TransactionProposalItem(
                type=item.type,
                amount=item.amount,
                currency=currency,
                category_id=category.id,
                **await category_labels(session, user_id, category),
                occurred_on=item.occurred_on,
                note=(item.note or "").strip() or None,
            )
        )
    if items == payload.items:
        return payload
    return TransactionProposalPayload(
        items=items, original_items=payload.original_items or payload.items
    )


async def _confirm_transactions(
    session: AsyncSession, user_id: UUID, proposal: Proposal, edits: ConfirmIn | None
) -> list[Transaction]:
    payload = TransactionProposalPayload.model_validate(proposal.payload)
    if edits is not None and (edits.amount is not None or edits.recurring is not None):
        raise InvalidInputError("Tę propozycję można zmienić tylko w polach transakcji")
    if edits is not None and edits.items is not None:
        payload = await _apply_item_edits(session, user_id, payload, edits.items)
        proposal.payload = payload.model_dump(mode="json")
    created = []
    for item in payload.items:
        category = await categories_repo.get_for_user(session, user_id, item.category_id)
        if category is None or category.archived_at is not None or category.kind != item.type:
            raise InvalidInputError(f"Kategoria „{item.category}” nie jest już dostępna")
        created.append(
            await tx_repo.add(
                session,
                Transaction(
                    user_id=user_id,
                    type=item.type,
                    amount=item.amount,
                    currency=item.currency,
                    category_id=item.category_id,
                    occurred_on=item.occurred_on,
                    note=item.note,
                    source=TransactionSource.ASSISTANT,
                    proposal_id=proposal.id,
                ),
            )
        )
    return created


async def _confirm_budget(
    session: AsyncSession, user_id: UUID, proposal: Proposal, edits: ConfirmIn | None
) -> Budget:
    payload = BudgetProposalPayload.model_validate(proposal.payload)
    if edits is not None and (edits.items is not None or edits.recurring is not None):
        raise InvalidInputError("W propozycji budżetu można zmienić tylko kwotę")
    if edits is not None and edits.amount is not None and edits.amount != payload.amount:
        payload = payload.model_copy(
            update={"amount": edits.amount, "original_amount": payload.amount}
        )
        proposal.payload = payload.model_dump(mode="json")
    category = await categories_repo.get_for_user(session, user_id, payload.category_id)
    if category is None or category.archived_at is not None:
        raise InvalidInputError(f"Kategoria „{payload.category}” nie jest już dostępna")
    await session.execute(
        insert(Budget)
        .values(
            user_id=user_id,
            category_id=payload.category_id,
            amount=payload.amount,
            period=BudgetPeriod.MONTHLY,
        )
        .on_conflict_do_update(
            constraint="uq_budgets_user_category_period",
            set_={"amount": payload.amount, "updated_at": datetime.now(UTC)},
        )
    )
    budget = await analytics_repo.budget_for_category(session, user_id, payload.category_id)
    assert budget is not None
    await session.refresh(budget)
    return budget


async def _apply_recurring_edits(
    session: AsyncSession,
    user_id: UUID,
    payload: RecurringProposalPayload,
    edited: EditedRecurring,
    today: date,
) -> RecurringProposalPayload:
    category = await recurring_service.checked_category(
        session, user_id, edited.category_id, payload.type
    )
    draft = RecurringDraft(
        type=payload.type,
        amount=edited.amount,
        currency=payload.currency,
        category_id=category.id,
        **await category_labels(session, user_id, category),
        name=edited.name.strip(),
        frequency=edited.frequency,
        day_of_month=edited.day_of_month,
        month=edited.month,
        first_payment_on=recurring_service.first_due(edited, today),
    )
    current = RecurringDraft.model_validate(payload.model_dump(exclude={"original"}))
    if draft.model_dump(exclude={"first_payment_on"}) == current.model_dump(
        exclude={"first_payment_on"}
    ):
        return payload
    return RecurringProposalPayload(**draft.model_dump(), original=payload.original or current)


async def _confirm_recurring(
    session: AsyncSession, user_id: UUID, proposal: Proposal, edits: ConfirmIn | None
) -> RecurringRule:
    payload = RecurringProposalPayload.model_validate(proposal.payload)
    if edits is not None and (edits.items is not None or edits.amount is not None):
        raise InvalidInputError("W stałej płatności zmieniasz pola płatności, nie transakcji")
    today = date.today()
    if edits is not None and edits.recurring is not None:
        payload = await _apply_recurring_edits(session, user_id, payload, edits.recurring, today)
        proposal.payload = payload.model_dump(mode="json")
    rule = await recurring_service.create(
        session,
        user_id,
        RecurringCreate(
            type=payload.type,
            amount=payload.amount,
            category_id=payload.category_id,
            name=payload.name,
            frequency=payload.frequency,
            day_of_month=payload.day_of_month,
            month=payload.month,
        ),
        today,
    )
    return rule


async def confirm(
    session: AsyncSession, user_id: UUID, proposal_id: UUID, edits: ConfirmIn | None = None
) -> ConfirmResult:
    proposal = await _pending(session, user_id, proposal_id)
    result = ConfirmResult(proposal=proposal)
    if proposal.kind == ProposalKind.TRANSACTION:
        result.transactions = await _confirm_transactions(session, user_id, proposal, edits)
    elif proposal.kind == ProposalKind.BUDGET:
        result.budget = await _confirm_budget(session, user_id, proposal, edits)
    else:
        result.recurring = await _confirm_recurring(session, user_id, proposal, edits)
    proposal.status = ProposalStatus.CONFIRMED
    proposal.confirmed_at = datetime.now(UTC)
    await session.flush()
    return result


async def reject(session: AsyncSession, user_id: UUID, proposal_id: UUID) -> Proposal:
    proposal = await _pending(session, user_id, proposal_id)
    proposal.status = ProposalStatus.REJECTED
    await session.flush()
    return proposal
