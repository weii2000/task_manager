from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    pool_size=20,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


async def get_auth_db():
    async with AsyncSessionLocal() as db:
        yield db