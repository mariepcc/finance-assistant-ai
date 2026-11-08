import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, false, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, pg_enum
from app.models.enums import TransactionType


class Category(UUIDPk, Timestamps, Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index(
            "uq_categories_user_kind_name",
            "user_id",
            "kind",
            text("lower(name)"),
            unique=True,
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[TransactionType] = mapped_column(pg_enum(TransactionType, "transaction_type"))
    icon: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=false())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
