from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from .config import settings

# Create an async engine
async_engine = create_async_engine(
    url=settings.database_url,
    echo=False,  # Set to True to see SQL queries
)

# Create a session maker
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get a database session.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
