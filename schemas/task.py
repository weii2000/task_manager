from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.datetime_utils import restore_utc_aware, to_utc_naive
from models.enums import CreationSource, TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    plan_id: int | None = Field(default=None, gt=0)
    parent_task_id: int | None = Field(default=None, gt=0)

    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    acceptance_criteria: str | None = Field(
        default=None,
        max_length=5000,
    )

    sort_order: int = Field(default=0, ge=0)
    priority: TaskPriority = TaskPriority.LOW

    start_time: datetime | None = None
    due_time: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("任务标题不能为空")
        return value

    @field_validator("start_time", "due_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return to_utc_naive(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_time is not None
            and self.due_time is not None
            and self.due_time < self.start_time
        ):
            raise ValueError("截止时间不能早于开始时间")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    acceptance_criteria: str | None = Field(
        default=None,
        max_length=5000,
    )

    sort_order: int | None = Field(default=None, ge=0)
    priority: TaskPriority | None = None

    start_time: datetime | None = None
    due_time: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("任务标题不能设置为空")

        value = value.strip()
        if not value:
            raise ValueError("任务标题不能为空")
        return value

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("任务顺序不能设置为空")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(
        cls,
        value: TaskPriority | None,
    ) -> TaskPriority:
        if value is None:
            raise ValueError("任务优先级不能设置为空")
        return value

    @field_validator("start_time", "due_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return to_utc_naive(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if (
            self.start_time is not None
            and self.due_time is not None
            and self.due_time < self.start_time
        ):
            raise ValueError("截止时间不能早于开始时间")
        return self


class TaskStatusUpdate(BaseModel):
    status: TaskStatus

    model_config = ConfigDict(extra="forbid")


class TaskRead(BaseModel):
    task_id: int
    plan_id: int
    parent_task_id: int | None
    level: int = Field(ge=1, le=3)

    title: str
    description: str | None
    acceptance_criteria: str | None

    sort_order: int
    status: TaskStatus
    priority: TaskPriority
    creation_source: CreationSource

    start_time: datetime | None
    due_time: datetime | None
    completed_time: datetime | None
    archived_time: datetime | None
    created_time: datetime
    updated_time: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator(
        "start_time",
        "due_time",
        "completed_time",
        "archived_time",
        "created_time",
        "updated_time",
        mode="before",
    )
    @classmethod
    def restore_utc_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return restore_utc_aware(value)
