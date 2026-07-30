from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import TaskStatus
from models.plan import Plan
from models.task import Task


async def create_task_by_data(
    task_data: dict,
    db: AsyncSession,
) -> Task:
    task = Task(**task_data)
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


async def get_task_by_id_and_owner_user_id(
    task_id: int,
    owner_user_id: int,
    db: AsyncSession,
) -> Task | None:
    result = await db.execute(
        select(Task)
        .join(
            Plan,
            Task.plan_id == Plan.plan_id,
        )
        .where(
            Task.task_id == task_id,
            Plan.owner_user_id == owner_user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_tasks_by_plan_id_and_owner_user_id(
    plan_id: int,
    owner_user_id: int,
    db: AsyncSession,
    archived: bool = False,
) -> list[Task]:
    archive_condition = (
        Task.archived_time.is_not(None)
        if archived
        else Task.archived_time.is_(None)
    )

    result = await db.execute(
        select(Task)
        .join(
            Plan,
            Task.plan_id == Plan.plan_id,
        )
        .where(
            Task.plan_id == plan_id,
            Plan.owner_user_id == owner_user_id,
            archive_condition,
        )
        .order_by(
            Task.sort_order.asc(),
            Task.created_time.asc(),
        )
    )
    return list(result.scalars().all())


async def count_tasks_by_plan_id(
    plan_id: int,
    db: AsyncSession,
) -> int:
    result = await db.execute(
        select(func.count(Task.task_id)).where(
            Task.plan_id == plan_id,
        )
    )
    return result.scalar_one()


async def update_task_by_data(
    task: Task,
    update_data: dict,
    db: AsyncSession,
) -> Task:
    for field, value in update_data.items():
        setattr(task, field, value)

    await db.flush()
    await db.refresh(task)
    return task


async def has_incomplete_child_tasks(
    parent_task_id: int,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(
            exists().where(
                Task.parent_task_id == parent_task_id,
                Task.archived_time.is_(None),
                Task.status.notin_(
                    (
                        TaskStatus.COMPLETED,
                        TaskStatus.CANCELLED,
                    )
                ),
            )
        )
    )
    return result.scalar_one()


async def has_incomplete_plan_tasks(
    plan_id: int,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(
            exists().where(
                Task.plan_id == plan_id,
                Task.archived_time.is_(None),
                Task.status.notin_(
                    (
                        TaskStatus.COMPLETED,
                        TaskStatus.CANCELLED,
                    )
                ),
            )
        )
    )
    return result.scalar_one()


async def has_unarchived_child_tasks(
    parent_task_id: int,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(
            exists().where(
                Task.parent_task_id == parent_task_id,
                Task.archived_time.is_(None),
            )
        )
    )
    return result.scalar_one()
