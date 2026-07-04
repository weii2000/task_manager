from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship


from models.base import Base
from models.enums import CreationSource, TaskPriority, TaskStatus


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "sort_order >= 0",
            name="ck_tasks_nonnegative_sort_order",
        ),
        CheckConstraint(
            "start_time IS NULL OR due_time IS NULL OR due_time >= start_time",
            name="ck_tasks_due_after_start",
        ),
    )

    task_id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True
    )
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.project_id"),
        nullable=False,
        index=True,
    )
    parent_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tasks.task_id"),
        nullable=True,
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
    acceptance_criteria: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(
            TaskStatus,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=TaskStatus.TODO,
        nullable=False,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(
            TaskPriority,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=TaskPriority.LOW,
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
    project: Mapped["Project"] = relationship( # type: ignore
        "Project",
        back_populates="tasks",
    )
    parent: Mapped["Task | None"] = relationship(
        "Task",
        back_populates="children",
        remote_side=[task_id],
    )
    children: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent",
    )
