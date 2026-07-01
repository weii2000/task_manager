from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth import RefreshToken


async def create_refresh_token_record(token_hash: str, expires_at: datetime, user_id: int, db: AsyncSession):
    refresh_token = RefreshToken(token_hash=token_hash, expires_at=expires_at, user_id=user_id)
    db.add(refresh_token)
    await db.flush()
    await db.refresh(refresh_token)

    return refresh_token


async def get_refresh_token_by_token_hash(token_hash: str, db: AsyncSession):
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    result = await db.execute(stmt)
    refresh_token = result.scalar_one_or_none()

    return refresh_token


async def revoke_token_by_token_hash(token_hash: str, db: AsyncSession) -> RefreshToken | None:
    refresh_token = await get_refresh_token_by_token_hash(token_hash, db)
    
    if not refresh_token:
        return None
    
    if refresh_token.revoked_at is not None:
        return None
    
    refresh_token.revoked_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(refresh_token)
    
    return refresh_token

