from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from agent.runtime.context import AgentRunContext
from agent.runtime.state import AvailableTool
from agent.tools.plan import (
    get_plan_task_tree,
    list_user_plans,
)
from agent.tools.schemas import (
    GetPlanTaskTreeInput,
    ListUserPlansInput,
)


@dataclass(frozen=True)
class ToolDefinition:
    description: str
    input_schema: type[BaseModel]
    handler: Callable[[AgentRunContext, Any], Awaitable[Any]]


TOOL_REGISTRY: dict[AvailableTool, ToolDefinition] = {
    AvailableTool.LIST_USER_PLANS: ToolDefinition(
        description="查询当前用户已有计划，可按标题、描述或目标进行模糊搜索。",
        input_schema=ListUserPlansInput,
        handler=list_user_plans,
    ),
    AvailableTool.GET_PLAN_TASK_TREE: ToolDefinition(
        description="查询指定计划的任务树，用于理解已有任务结构并避免重复规划。",
        input_schema=GetPlanTaskTreeInput,
        handler=get_plan_task_tree,
    ),
}


def get_tool_definition(tool_name: AvailableTool) -> ToolDefinition:
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
