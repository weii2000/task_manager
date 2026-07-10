from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.enums import ProjectStatus, TaskPriority, TaskStatus


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListUserProjectsInput(ToolInput):
    keyword: str | None = Field(default=None, max_length=200)


class GetProjectTaskTreeInput(ToolInput):
    project_id: int = Field(gt=0)


class AgentProjectRead(BaseModel):
    project_id: int | None
    title: str
    description: str | None
    goal: str | None
    status: ProjectStatus
    start_time: datetime | None
    due_time: datetime | None
    completed_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AgentTaskRead(BaseModel):
    task_id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    acceptance_criteria: str | None = None
    children: list[AgentTaskRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AgentProjectOverview(BaseModel):
    project_id: int
    task_tree: list[AgentTaskRead]
