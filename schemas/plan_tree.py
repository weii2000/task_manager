from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from core.datetime_utils import to_utc_naive
from models.enums import TaskPriority, TaskStatus
from schemas.plan import PlanCreate


class PlanTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    acceptance_criteria: str | None = Field(default=None, max_length=5000)
    level: int = Field(ge=1, le=3)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.LOW
    start_time: datetime | None = None
    due_time: datetime | None = None
    subtasks: list[PlanTaskCreate] = Field(default_factory=list)

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
    def normalize_task_time(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        return to_utc_naive(value)

    @model_validator(mode="after")
    def validate_task_time_range(self) -> PlanTaskCreate:
        if (
            self.start_time is not None
            and self.due_time is not None
            and self.due_time < self.start_time
        ):
            raise ValueError("截止时间不能早于开始时间")
        return self


class PlanTreeCreate(PlanCreate):
    tasks: list[PlanTaskCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_task_tree_limits(self) -> PlanTreeCreate:
        task_count = 0

        def visit(tasks: list[PlanTaskCreate], depth: int) -> None:
            nonlocal task_count
            for task in tasks:
                if task.level != depth:
                    raise ValueError("任务 level 必须与嵌套层级一致")
                task_count += 1
                if task_count > 100:
                    raise ValueError("任务总数不能超过 100 个")
                visit(task.subtasks, depth + 1)

        visit(self.tasks, 1)
        return self


class PlanResult(BaseModel):
    plan_id: int = Field(gt=0)
    plan_title: str = Field(min_length=1, max_length=100)
    created_task_count: int = Field(ge=1, le=100)
