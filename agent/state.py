from __future__ import annotations
from datetime import datetime
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    SYSTEM = auto()
    USER = auto()
    ASSISTANT = auto()
    TOOL = auto()


class Message(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=5000)


class Action(StrEnum):
    THINK = auto()
    USE_TOOL = auto()
    CLARIFY = auto()
    PAUSE = auto()
    RESUME = auto()
    FINISH = auto()


class AvailableTool(StrEnum):
    LIST_USER_PROJECTS = auto()
    GET_PROJECT_TASK_TREE = auto()


class ToolCall(BaseModel):
    tool_name: AvailableTool
    parameter: dict[str, Any]


class ResponseMessage(Message):
    next_action: Action
    tool_calls: list[ToolCall] = Field(default_factory=list)


class PlanningInfo(BaseModel):
    goal: str | None = None
    acceptance_criteria: str | None = None
    constraints: list[str] | None = None


class PlanningTask(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = None
    start_time: datetime | None = None
    due_time: datetime | None = None
    subtasks: list[PlanningTask] = Field(default_factory=list)


class PlanningDraft(BaseModel):
    tasks: list[PlanningTask] = Field(default_factory=list)


class State(BaseModel):
    messages: list[Message | ResponseMessage]
    available_tools: list[AvailableTool] = Field(default_factory=lambda: list(AvailableTool))
    info: PlanningInfo
    draft: PlanningDraft
