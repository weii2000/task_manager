from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship


from models.base import Base
from models.enums import CreationSource, ProjectStatus, ProjectSystemType


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "start_time IS NULL OR due_time IS NULL OR due_time >= start_time",
            name="ck_projects_due_after_start",
        ),
        UniqueConstraint(
            "owner_user_id",
            "system_type",
            name="uq_projects_owner_system_type",
        ),
    )

    project_id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
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
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(
            ProjectStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=ProjectStatus.PLANNING,
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
    system_type: Mapped[ProjectSystemType | None] = mapped_column(
        SAEnum(
            ProjectSystemType,
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
    owner: Mapped["User"] = relationship( # type: ignore
        "User",
        back_populates="projects",
    )
    tasks: Mapped[list["Task"]] = relationship( # type: ignore
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
    )
