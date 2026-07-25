from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import decode_token
from crud.user import get_user_by_user_id
from database.session import get_auth_db
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_auth_db),
) -> User:
    subject = decode_token(token, "access")

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或已过期的 token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(subject)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 内容无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_user_id(user_id, db)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user