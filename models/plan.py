from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base
from models.enums import CreationSource, PlanStatus, PlanSystemType

if TYPE_CHECKING:
    from models.task import Task
    from models.user import User


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "start_time IS NULL OR due_time IS NULL OR due_time >= start_time",
            name="ck_plans_due_after_start",
        ),
        UniqueConstraint(
            "owner_user_id",
            "system_type",
            name="uq_plans_owner_system_type",
        ),
        UniqueConstraint(
            "source_agent_session_id",
            name="uq_plans_source_agent_session_id",
        ),
        UniqueConstraint(
            "owner_user_id",
            "idempotency_key",
            name="uq_plans_owner_idempotency_key",
        ),
    )

    plan_id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )
    source_agent_session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agent_session.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(100), 
        index=True, 
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text, 
        nullable=True
    )
    goal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    status: Mapped[PlanStatus] = mapped_column(
        SAEnum(
            PlanStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=PlanStatus.PLANNING,
        nullable=False,
    )
    creation_source: Mapped[CreationSource] = mapped_column(
        SAEnum(
            CreationSource,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=CreationSource.MANUAL,
        nullable=False,
    )
    system_type: Mapped[PlanSystemType | None] = mapped_column(
        SAEnum(
            PlanSystemType,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=True,
    )
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    due_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    completed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    archived_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="plans",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
