from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="queued",
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
