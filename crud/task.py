from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


from models.task import Task


async def get_task_by_task_id_user_id(task_id: int, db: AsyncSession, user_id: int | None = None):
    stmt = select(Task).where(Task.task_id == task_id)
    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    return task


async def task_complete_update_by_task(task: Task, complete_update: bool, db: AsyncSession):
    task.completed = complete_update
    await db.flush()


async def create_task_by_given_dict(task_create: dict, db: AsyncSession):
    task = Task(**task_create)
    db.add(task)
    await db.flush()
    await db.refresh(task)

    return task


async def delete_task_by_task(task: Task, db: AsyncSession):
    await db.delete(task)
    await db.flush()


async def get_tasks_by_user_id(
        user_id: int, 
        db: AsyncSession, 
        completed: bool | None = None, 
        tag: str | None = None
    ):
    stmt = select(Task).where(Task.user_id == user_id).order_by(Task.created_time.desc())

    if completed is not None:
        stmt = stmt.where(Task.completed == completed)

    if tag is not None:
        stmt = stmt.where(Task.tag == tag)

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return tasks