import asyncio
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import MagicMock

from src.main import app
from src.database import get_db_session
from src.config import settings
from src.models import Base
from src.services.storage_service import (
    storage_service,
    StorageService,
)

# Use a separate database for testing
TEST_DATABASE_URL = str(settings.database_url)

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=AsyncSession
)


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency override for test database sessions.
    """
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def mock_storage_service():
    mock = MagicMock(spec=StorageService)
    mock.upload_file.return_value = None
    mock.get_presigned_url.side_effect = lambda name: f"http://mock-storage/{name}"
    return mock


app.dependency_overrides[get_db_session] = override_get_db_session


@pytest.fixture(scope="session")
def event_loop():
    """
    Creates an instance of the default event loop for each test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database(event_loop: asyncio.AbstractEventLoop):
    """
    Create and drop the test database tables for the test session.
    """

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    event_loop.run_until_complete(setup())
    yield
    event_loop.run_until_complete(teardown())


@pytest.fixture(scope="function")
async def client(mock_storage_service: MagicMock) -> AsyncGenerator[AsyncClient, None]:
    """
    An async client for making requests to the app.
    """
    from src.services import track_service

    track_service.storage_service = mock_storage_service
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    # restore original service
    track_service.storage_service = storage_service
