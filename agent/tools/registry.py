from agent.state import AvailableTool
from agent.tools.base import ToolHandler
from agent.tools.project import (
    get_project_task_tree,
    list_user_projects,
)


TOOL_REGISTRY: dict[AvailableTool, ToolHandler] = {
    AvailableTool.LIST_USER_PROJECTS: list_user_projects,
    AvailableTool.GET_PROJECT_TASK_TREE: get_project_task_tree,
}


def get_tool_handler(tool_name: AvailableTool) -> ToolHandler:
    return TOOL_REGISTRY[tool_name]
