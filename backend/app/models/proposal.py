import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, pg_enum
from app.models.enums import ProposalKind, ProposalStatus


class Proposal(UUIDPk, Timestamps, Base):
    __tablename__ = "proposals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ProposalKind] = mapped_column(pg_enum(ProposalKind, "proposal_kind"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[ProposalStatus] = mapped_column(
        pg_enum(ProposalStatus, "proposal_status"), server_default="pending"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
