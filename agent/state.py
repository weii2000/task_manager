from __future__ import annotations
from datetime import datetime
from enum import StrEnum, auto
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class MessageRole(StrEnum):
    SYSTEM = auto()
    USER = auto()
    ASSISTANT = auto()


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
    call_id: str = Field(default_factory=lambda: uuid4().hex)
    tool_name: AvailableTool
    parameter: dict[str, Any]


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


class AgentDecision(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    next_action: Action
    tool_calls: list[ToolCall] = Field(default_factory=list)
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)

    @model_validator(mode="after")
    def validate_tool_calls_match_action(self) -> AgentDecision:
        if self.next_action == Action.USE_TOOL and not self.tool_calls:
            raise ValueError("use_tool action requires at least one tool call")
        if self.next_action != Action.USE_TOOL and self.tool_calls:
            raise ValueError("tool calls are only allowed for use_tool action")
        if self.next_action not in {
            Action.CLARIFY,
            Action.USE_TOOL,
            Action.FINISH,
        }:
            raise ValueError("unsupported model action")
        return self


class ToolResultStatus(StrEnum):
    SUCCESS = auto()
    ERROR = auto()


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class ToolResult(BaseModel):
    call_id: str
    tool_name: AvailableTool
    arguments: dict[str, Any]
    status: ToolResultStatus
    output: Any | None = None
    error: ToolError | None = None


class State(BaseModel):
    messages: list[Message]
    available_tools: list[AvailableTool] = Field(default_factory=lambda: list(AvailableTool))
    info: PlanningInfo = Field(default_factory=PlanningInfo)
    draft: PlanningDraft = Field(default_factory=PlanningDraft)
    next_action: Action = Action.THINK
    pending_tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
