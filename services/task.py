from crud.task import create_task_by_given_dict, delete_task_by_task, get_task_by_task_id_user_id, get_tasks_by_user_id, task_complete_update_by_task
from crud.user import get_user_by_user_id
from exceptions.task import TaskNotFoundError
from exceptions.user import UserNotFoundError
from schemas.task import TaskCompleteUpdate, TaskCreate, TaskRead
from sqlalchemy.ext.asyncio import AsyncSession


async def create_task_for_user(task_create: TaskCreate, user_id: int, db: AsyncSession):
    data = task_create.model_dump()

    async with db.begin():
        user = await get_user_by_user_id(user_id, db)
        if not user:
            raise UserNotFoundError()

        data["user_id"] = user_id
        task = await create_task_by_given_dict(data, db)
        await db.refresh(task)
    return TaskRead.model_validate(task)


async def complete_task_for_user(task_complete_update: TaskCompleteUpdate, user_id: int, db: AsyncSession):
    async with db.begin():
        task = await get_task_by_task_id_user_id(task_complete_update.task_id, db, user_id)
        if not task:
            raise TaskNotFoundError()

        await task_complete_update_by_task(task, task_complete_update.completed, db)
        await db.refresh(task)
    return TaskRead.model_validate(task)


async def delete_task_for_user(task_id: int, user_id: int, db: AsyncSession):
    async with db.begin():
        task = await get_task_by_task_id_user_id(task_id, db, user_id)
        if not task:
            raise TaskNotFoundError()

        await delete_task_by_task(task, db)


async def get_tasks_for_user(
        user_id: int,
        db: AsyncSession,
        completed: bool | None = None,
        tag: str | None = None,
    ):
    tasks = await get_tasks_by_user_id(user_id, db, completed, tag)
    return [TaskRead.model_validate(task) for task in tasks]
