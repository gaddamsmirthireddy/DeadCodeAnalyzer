from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    line_number: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="static",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
