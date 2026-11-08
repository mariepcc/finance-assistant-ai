import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps


class Profile(Timestamps, Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    default_currency: Mapped[str] = mapped_column(CHAR(3), server_default="PLN")
    gdpr_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
