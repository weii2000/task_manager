from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from crud.plan import (
    create_plan_by_data,
    get_plan_by_idempotency_key,
)
from crud.task import count_tasks_by_plan_id, create_task_by_data
from models.enums import CreationSource, PlanStatus
from schemas.plan_tree import (
    PlanResult,
    PlanTaskCreate,
    PlanTreeCreate,
)


async def _result_for_plan(
    plan_id: int,
    plan_title: str,
    db: AsyncSession,
) -> PlanResult:
    return PlanResult(
        plan_id=plan_id,
        plan_title=plan_title,
        created_task_count=await count_tasks_by_plan_id(plan_id, db),
    )


async def persist_plan_tree(
    plan: PlanTreeCreate,
    idempotency_key: str,
    user_id: int,
    db: AsyncSession,
    source_agent_session_id: int | None = None,
) -> PlanResult:
    existing = await get_plan_by_idempotency_key(
        user_id,
        idempotency_key,
        db,
    )
    if existing is not None:
        return await _result_for_plan(
            existing.plan_id,
            existing.title,
            db,
        )

    created_plan = await create_plan_by_data(
        {
            **plan.model_dump(exclude={"tasks"}),
            "owner_user_id": user_id,
            "status": PlanStatus.ACTIVE,
            "creation_source": CreationSource.AGENT,
            "source_agent_session_id": source_agent_session_id,
            "idempotency_key": idempotency_key,
        },
        db,
    )
    created_task_count = 0

    async def create_task_tree(
        tasks: list[PlanTaskCreate],
        parent_task_id: int | None = None,
    ) -> None:
        nonlocal created_task_count
        for sort_order, planned_task in enumerate(tasks):
            task = await create_task_by_data(
                {
                    **planned_task.model_dump(exclude={"subtasks"}),
                    "plan_id": created_plan.plan_id,
                    "parent_task_id": parent_task_id,
                    "sort_order": sort_order,
                    "creation_source": CreationSource.AGENT,
                },
                db,
            )
            created_task_count += 1
            await create_task_tree(
                planned_task.subtasks,
                parent_task_id=task.task_id,
            )

    await create_task_tree(plan.tasks)
    return PlanResult(
        plan_id=created_plan.plan_id,
        plan_title=created_plan.title,
        created_task_count=created_task_count,
    )


async def create_plan_tree_for_user(
    plan: PlanTreeCreate,
    idempotency_key: str,
    user_id: int,
    db: AsyncSession,
) -> PlanResult:
    try:
        async with db.begin():
            return await persist_plan_tree(
                plan,
                idempotency_key,
                user_id,
                db,
            )
    except IntegrityError:
        async with db.begin():
            existing = await get_plan_by_idempotency_key(
                user_id,
                idempotency_key,
                db,
            )
            if existing is None:
                raise
            return await _result_for_plan(
                existing.plan_id,
                existing.title,
                db,
            )
