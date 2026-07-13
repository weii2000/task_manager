from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import MemoryStatus
from models.memory import UserMemory
from models.user import User


async def create_memory_by_data(
    memory_data: dict,
    db: AsyncSession,
) -> UserMemory:
    memory = UserMemory(**memory_data)
    db.add(memory)
    await db.flush()
    await db.refresh(memory)
    return memory


async def get_memories_by_user_id_and_status(
    user_id: int,
    status: MemoryStatus,
    db: AsyncSession,
    *,
    limit: int | None = None,
    for_update: bool = False,
) -> list[UserMemory]:
    statement = (
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.status == status,
        )
        .order_by(
            UserMemory.updated_time.desc(),
            UserMemory.memory_id.desc(),
        )
    )
    if limit is not None:
        statement = statement.limit(limit)
    if for_update:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )

    result = await db.execute(statement)
    return list(result.scalars().all())


async def get_memory_by_id_and_user_id(
    memory_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    for_update: bool = False,
) -> UserMemory | None:
    statement = select(UserMemory).where(
        UserMemory.memory_id == memory_id,
        UserMemory.user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )

    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def update_memory_by_data(
    memory: UserMemory,
    update_data: dict,
    db: AsyncSession,
) -> UserMemory:
    for field, value in update_data.items():
        setattr(memory, field, value)

    await db.flush()
    await db.refresh(memory)
    return memory


async def lock_user_for_memory_update(
    user_id: int,
    db: AsyncSession,
) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()
