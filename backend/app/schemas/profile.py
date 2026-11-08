from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import Currency, ORMModel


class ProfileOut(ORMModel):
    id: UUID
    display_name: str | None
    default_currency: str
    gdpr_consent_at: datetime | None


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    default_currency: Currency | None = None


class ConsentIn(BaseModel):
    accepted: bool
    default_currency: Currency = "PLN"
