from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


async def get_user_by_username(username: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    return user


async def create_user(username: str, hashed_password: str, db :AsyncSession) -> User:
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def get_user_by_user_id(user_id: int, db: AsyncSession) -> User | None:
    user = await db.get(User, user_id)
    return user


async def update_user_info_by_dict(user_info_update_dict: dict, user_id: int, db: AsyncSession) -> User | None:
    stmt = (
        update(User)
        .where(User.user_id == user_id)
        .values(**user_info_update_dict)
    )
    await db.execute(stmt)
    await db.flush()
    user = await get_user_by_user_id(user_id, db)
    return user