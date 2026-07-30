from agent.runtime.context import AgentRunContext
from agent.tools.schemas import (
    AgentPlanOverview,
    AgentPlanRead,
    AgentTaskRead,
    GetPlanTaskTreeInput,
    ListUserPlansInput,
)
from schemas.task import TaskRead
from services.plan import get_plans_for_user
from services.task import get_plan_tasks_for_user


async def list_user_plans(
    context: AgentRunContext,
    arguments: ListUserPlansInput,
) -> list[AgentPlanRead]:
    result = await get_plans_for_user(
        context.user_id,
        context.db,
        keyword=arguments.keyword,
    )
    plans = [
        AgentPlanRead.model_validate(plan)
        for plan in result
    ]
    return plans


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


async def get_plan_task_tree(
    context: AgentRunContext,
    arguments: GetPlanTaskTreeInput,
) -> AgentPlanOverview:
    tasks = await get_plan_tasks_for_user(
        context.user_id,
        context.db,
        arguments.plan_id,
    )
    task_tree = build_task_tree(tasks)
    return AgentPlanOverview(
        plan_id=arguments.plan_id,
        task_tree=task_tree,
    )
