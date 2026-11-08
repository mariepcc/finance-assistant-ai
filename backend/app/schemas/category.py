from uuid import UUID

from app.models.enums import TransactionType
from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: UUID
    name: str
    kind: TransactionType
    icon: str | None
    color: str | None
    is_default: bool
