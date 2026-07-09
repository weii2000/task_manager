from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel, Field

from models.enums import ProjectStatus, TaskPriority, TaskStatus


class AgentProjectRead(BaseModel):
    project_id: int | None
    title: str
    description: str | None
    goal: str | None
    status: ProjectStatus
    start_time: datetime | None
    due_time: datetime | None
    completed_time: datetime | None


class AgentTaskRead(BaseModel):
    task_id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    acceptance_criteria: str | None = None
    children: list[AgentTaskRead] = Field(default_factory=list)


class AgentProjectOverview(BaseModel):
    project_id: int | None
    task_tree: list[AgentTaskRead]
