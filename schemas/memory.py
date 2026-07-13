from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from core.datetime_utils import restore_utc_aware
from models.enums import MemoryCategory, MemorySource, MemoryStatus


class MemoryIngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("记忆内容不能为空")
        return value


class MemoryUpdateRequest(BaseModel):
    category: MemoryCategory | None = None
    content: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("记忆内容不能为空")
        return value

    @model_validator(mode="after")
    def validate_update_fields(self) -> "MemoryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if "category" in self.model_fields_set and self.category is None:
            raise ValueError("记忆分类不能设置为空")
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("记忆内容不能设置为空")
        return self


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    memory_id: int
    category: MemoryCategory
    content: str
    status: MemoryStatus
    source: MemorySource
    version: int
    source_agent_session_id: int | None
    source_message_index: int | None
    created_time: datetime
    updated_time: datetime

    @field_validator("created_time", "updated_time", mode="before")
    @classmethod
    def restore_utc_timezone(cls, value: datetime) -> datetime:
        return restore_utc_aware(value)


class MemoryIngestResponse(BaseModel):
    created: list[MemoryRead] = Field(default_factory=list)
    updated: list[MemoryRead] = Field(default_factory=list)
    ignored_count: int = Field(default=0, ge=0)


class MemoryConfirmationRequest(BaseModel):
    approved: bool

    model_config = ConfigDict(extra="forbid")


class MemoryConfirmationResponse(BaseModel):
    candidate: MemoryRead
    created: list[MemoryRead] = Field(default_factory=list)
    updated: list[MemoryRead] = Field(default_factory=list)
    ignored_count: int = Field(default=0, ge=0)
