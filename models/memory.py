from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.enums import MemoryCategory, MemorySource, MemoryStatus

if TYPE_CHECKING:
    from models.user import User


class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (
        CheckConstraint(
            "version >= 1",
            name="ck_user_memories_positive_version",
        ),
        CheckConstraint(
            "source_message_index IS NULL OR source_message_index >= 0",
            name="ck_user_memories_nonnegative_message_index",
        ),
        Index(
            "ix_user_memories_user_status_updated",
            "user_id",
            "status",
            "updated_time",
        ),
    )

    memory_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[MemoryCategory] = mapped_column(
        SAEnum(
            MemoryCategory,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MemoryStatus] = mapped_column(
        SAEnum(
            MemoryStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=MemoryStatus.ACTIVE,
        nullable=False,
    )
    source: Mapped[MemorySource] = mapped_column(
        SAEnum(
            MemorySource,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    source_agent_session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_session.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_message_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="memories",
    )
