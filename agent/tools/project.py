from typing import Any

from agent.tools.base import ToolContext
from agent.tools.schemas import AgentProjectOverview, AgentProjectRead, AgentTaskRead
from schemas.task import TaskRead
from services.project import get_projects_for_user
from services.task import get_project_tasks_for_user


async def list_user_projects(
        context: ToolContext,
        parameter: dict[str, Any],
):
    result = await get_projects_for_user(context.user_id, context.db, keyword=parameter.get("keyword"))
    projects: list[AgentProjectRead] = [AgentProjectRead.model_validate(project) for project in result]
    return projects


def build_task_tree(tasks: list[TaskRead]) -> list[AgentTaskRead]:
    task_tree = []
    id_map: dict[int, AgentTaskRead] = {}
    for task in tasks:
        id_map[task.task_id] = AgentTaskRead.model_validate(task)
    
    for task in tasks:
        if task.parent_task_id is None:
            task_tree.append(id_map[task.task_id])
        else:
            id_map[task.parent_task_id].children.append(id_map[task.task_id])

    return task_tree


async def get_project_task_tree(
        context: ToolContext,
        parameter: dict[str, Any],
):
    project_id = parameter.get("project_id")
    tasks = await get_project_tasks_for_user(context.user_id, context.db, project_id)
    task_tree = build_task_tree(tasks)
    return AgentProjectOverview(project_id=project_id, task_tree=task_tree)


