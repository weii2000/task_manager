from datetime import datetime, timezone

from agent.runtime.context import AgentRunContext
from agent.runtime.state import ExecutionResult, PlanningTask, State
from exceptions.agent import AgentExecutionContextError
from schemas.plan_tree import (
    PlanTaskCreate,
    PlanTreeCreate,
)
from services.plan_tree import persist_plan_tree


def _adapt_task(task: PlanningTask, level: int) -> PlanTaskCreate:
    return PlanTaskCreate(
        **task.model_dump(exclude={"subtasks"}),
        level=level,
        subtasks=[
            _adapt_task(subtask, level + 1)
            for subtask in task.subtasks
        ],
    )


async def persist_plan(
    state: State,
    context: AgentRunContext,
) -> ExecutionResult:
    if context.session_id is None:
        raise AgentExecutionContextError()
    if state.draft.plan is None:
        raise AgentExecutionContextError("规划草稿缺少计划信息")
    if not state.draft.tasks:
        raise AgentExecutionContextError("规划草稿缺少可执行任务")

    planned_plan = state.draft.plan
    plan = PlanTreeCreate(
        title=planned_plan.title,
        description=planned_plan.description,
        goal=state.info.goal,
        start_time=planned_plan.start_time,
        due_time=planned_plan.due_time,
        tasks=[
            _adapt_task(task, 1)
            for task in state.draft.tasks
        ],
    )
    result = await persist_plan_tree(
        plan,
        f"agent-session:{context.session_id}",
        context.user_id,
        context.db,
        source_agent_session_id=context.session_id,
    )
    return ExecutionResult(
        plan_id=result.plan_id,
        plan_title=result.plan_title,
        created_task_count=result.created_task_count,
        completed_at=datetime.now(timezone.utc),
    )
