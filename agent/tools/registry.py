from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from agent.context import AgentRunContext
from agent.state import AvailableTool
from agent.tools.project import (
    get_project_task_tree,
    list_user_projects,
)
from agent.tools.schemas import (
    GetProjectTaskTreeInput,
    ListUserProjectsInput,
)


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class ToolDefinition(Generic[InputT, OutputT]):
    description: str
    input_schema: type[InputT]
    handler: Callable[[AgentRunContext, InputT], Awaitable[OutputT]]


TOOL_REGISTRY: dict[AvailableTool, ToolDefinition[Any, Any]] = {
    AvailableTool.LIST_USER_PROJECTS: ToolDefinition(
        description="查询当前用户已有项目，可按标题、描述或目标进行模糊搜索。",
        input_schema=ListUserProjectsInput,
        handler=list_user_projects,
    ),
    AvailableTool.GET_PROJECT_TASK_TREE: ToolDefinition(
        description="查询指定项目的任务树，用于理解已有任务结构并避免重复规划。",
        input_schema=GetProjectTaskTreeInput,
        handler=get_project_task_tree,
    ),
}


def get_tool_definition(tool_name: AvailableTool) -> ToolDefinition[Any, Any]:
    return TOOL_REGISTRY[tool_name]


def get_tool_specs(tool_names: list[AvailableTool]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool_name.value,
            "description": TOOL_REGISTRY[tool_name].description,
            "input_schema": TOOL_REGISTRY[tool_name].input_schema.model_json_schema(),
        }
        for tool_name in tool_names
    ]
