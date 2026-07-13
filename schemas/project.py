from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from core.datetime_utils import restore_utc_aware, to_utc_naive
from models.enums import CreationSource, ProjectStatus, ProjectSystemType


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    goal: str | None = Field(default=None, max_length=2000)
    start_time: datetime | None = None
    due_time: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("项目标题不能为空")
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


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    goal: str | None = Field(default=None, max_length=2000)
    start_time: datetime | None = None
    due_time: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("项目标题不能设置为空")

        value = value.strip()
        if not value:
            raise ValueError("项目标题不能为空")
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


class ProjectStatusUpdate(BaseModel):
    status: ProjectStatus

    model_config = ConfigDict(extra="forbid")


class ProjectRead(BaseModel):
    project_id: int
    owner_user_id: int
    title: str
    description: str | None
    goal: str | None
    status: ProjectStatus
    creation_source: CreationSource
    system_type: ProjectSystemType | None
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
