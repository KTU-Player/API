from datetime import date
from io import BytesIO

import pytest
from httpx import AsyncClient
from fastapi import status

from src.main import app
from src.dependencies import get_current_artist, get_current_premium_user, get_current_active_user
from src.models.user import Artist, FreeUser, BaseUser
from src.database import AsyncSessionFactory

# Sample users to be returned by dependency overrides
test_artist_user = Artist(
    user_id=3,
    email="artist@test.com",
    display_name="Test Artist",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    biography="A test artist",
    date_of_birth=date(1995, 5, 10),
    social_media_link="https://testartist.com",
    country_id=1,
)

test_premium_user = FreeUser(
    user_id=1,
    email="premium@test.com",
    display_name="Test Premium",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(1995, 5, 10),
)

test_active_user = BaseUser(
    user_id=1,
    email="active@test.com",
    display_name="Test Active User",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(1990, 1, 1),
)


async def override_get_current_artist():
    return test_artist_user


async def override_get_current_premium_user():
    return test_premium_user


async def override_get_current_active_user():
    return test_active_user


async def _create_test_track(db_session: AsyncSession, artist_id: int):
    """Helper to create a track for testing purposes."""
    new_track = Track(
        title="Test Track",
        is_explicit=False,
        audio_key="test/audio/key.mp3",
        cover_key="test/cover/key.jpg",
        artist_id=artist_id,
        duration_ms=1000,
    )
    db_session.add(new_track)
    await db_session.commit()
    await db_session.refresh(new_track)
    return new_track


@pytest.fixture(autouse=True, scope="function")
async def setup_users_for_deps():
    """
    Ensures the users our dependency mocks rely on exist in the test DB
    to satisfy any potential FK constraints during the request.
    """
    async with AsyncSessionFactory() as session:
        # Use merge to avoid primary key conflicts if user already exists from another test
        await session.merge(test_artist_user)
        await session.merge(test_premium_user)
        await session.merge(test_active_user)
        await session.commit()


@pytest.mark.asyncio
async def test_create_track_as_premium_user_fails(client: AsyncClient):
    app.dependency_overrides[get_current_artist] = override_get_current_premium_user

    response = await client.post(
        "/tracks",
        files={
            "audio_file": ("test.mp3", BytesIO(b"audio"), "audio/mpeg"),
            "cover_file": ("cover.jpg", BytesIO(b"image"), "image/jpeg"),
        },
        data={
            "title": "A Song by a Non-Artist",
            "is_explicit": "false",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_track_as_artist(client: AsyncClient, monkeypatch):
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    # Mock storage service
    monkeypatch.setattr(
        "src.services.storage_service.storage_service.upload_file",
        lambda file, bucket: f"http://fake-storage.com/{bucket}/{file.filename}",
    )

    response = await client.post(
        "/tracks",
        files={
            "audio_file": ("test.mp3", BytesIO(b"audio"), "audio/mpeg"),
            "cover_file": ("cover.jpg", BytesIO(b"image"), "image/jpeg"),
        },
        data={
            "title": "Test Track by Artist",
            "is_explicit": "true",
            "genre_ids": [1],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "Test Track by Artist"
    assert data["artist"]["display_name"] == "Test Artist"
    assert "test.mp3" in data["audio_url"]
    assert "cover.jpg" in data["cover_url"]

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_track_with_no_genres_fails(client: AsyncClient):
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    response = await client.post(
        "/tracks",
        files={
            "audio_file": ("test.mp3", BytesIO(b"audio"), "audio/mpeg"),
            "cover_file": ("cover.jpg", BytesIO(b"image"), "image/jpeg"),
        },
        data={
            "title": "Test Track with no genres",
            "is_explicit": "true",
            "genre_ids": [],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_update_track_with_no_genres_fails(client: AsyncClient):
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    response = await client.put(
        "/tracks/1",
        data={
            "genre_ids": [],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_log_track_play(client: AsyncClient):
    from src.dependencies import get_current_premium_user
    from src.models.activity import UserActivityEvent, StreamEvent
    from sqlalchemy import select

    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user

    async with AsyncSessionFactory() as session:
        test_track = await _create_test_track(session, test_artist_user.user_id)
        track_id = test_track.track_id

        # Get initial event counts
        initial_activity_event_count = (
            await session.scalar(select(func.count(UserActivityEvent.event_id)))
        )
        initial_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )

    response = await client.post(
        f"/tracks/{track_id}/log-play",
        json={"duration_milliseconds": 120000, "was_skipped": False},
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    async with AsyncSessionFactory() as session:
        # Verify a new UserActivityEvent was created
        final_activity_event_count = await session.scalar(
            select(func.count(UserActivityEvent.event_id))
        )
        assert final_activity_event_count == initial_activity_event_count + 1

        # Verify a new StreamEvent was created
        final_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )
        assert final_stream_event_count == initial_stream_event_count + 1

        # Verify the details of the created StreamEvent
        stream_event = await session.scalar(
            select(StreamEvent)
            .filter(StreamEvent.track_id == track_id)
            .order_by(StreamEvent.event_id.desc())
        )
        assert stream_event is not None
        assert stream_event.user_id == test_premium_user.user_id
        assert stream_event.duration_milliseconds == 120000
        assert stream_event.was_skipped is False
        assert stream_event.track_id == track_id

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_log_track_play_non_premium_user_fails(client: AsyncClient):
    from src.dependencies import get_current_free_user
    from src.models.user import FreeUser

    test_free_user = FreeUser(
        user_id=2,
        email="free@test.com",
        display_name="Test Free User",
        password_hash="hashed_password",
        last_login_date=date.today(),
        is_active=True,
        date_of_birth=date(1990, 1, 1),
    )

    async with AsyncSessionFactory() as session:
        await session.merge(test_free_user)
        await session.commit()
        test_track = await _create_test_track(session, test_artist_user.user_id)
        track_id = test_track.track_id

    async def override_get_current_free_user():
        return test_free_user

    app.dependency_overrides[get_current_premium_user] = override_get_current_free_user

    response = await client.post(
        f"/tracks/{track_id}/log-play",
        json={"duration_milliseconds": 60000, "was_skipped": True},
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_stream_track_does_not_create_stream_event(client: AsyncClient, monkeypatch):
    from src.dependencies import get_current_premium_user
    from src.models.activity import StreamEvent
    from sqlalchemy import select
    from minio.error import S3Error

    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user

    # Mock MinIO to avoid actual file operations
    monkeypatch.setattr(
        "src.services.storage_service.storage_service.client.stat_object",
        lambda bucket, obj: type("obj", (object,), {"size": 10000})(),
    )
    monkeypatch.setattr(
        "src.services.storage_service.storage_service.client.get_object",
        lambda bucket, obj, offset, length: BytesIO(b"test audio data"),
    )

    async with AsyncSessionFactory() as session:
        test_track = await _create_test_track(session, test_artist_user.user_id)
        track_id = test_track.track_id
        initial_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )

    response = await client.get(f"/tracks/{track_id}/stream-audio")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "audio/mpeg"

    async with AsyncSessionFactory() as session:
        final_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )
        assert final_stream_event_count == initial_stream_event_count

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_track_stream_url_does_not_create_stream_event(
    client: AsyncClient, monkeypatch
):
    from src.dependencies import get_current_premium_user
    from src.models.activity import StreamEvent
    from sqlalchemy import select

    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user

    # Mock get_presigned_url
    monkeypatch.setattr(
        "src.services.storage_service.storage_service.get_presigned_url",
        lambda audio_key, bucket: "http://presigned.url/test.mp3",
    )

    async with AsyncSessionFactory() as session:
        test_track = await _create_test_track(session, test_artist_user.user_id)
        track_id = test_track.track_id
        initial_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )

    response = await client.get(f"/tracks/{track_id}/stream-url")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["url"] == "http://presigned.url/test.mp3"

    async with AsyncSessionFactory() as session:
        final_stream_event_count = await session.scalar(
            select(func.count(StreamEvent.event_id))
        )
        assert final_stream_event_count == initial_stream_event_count

    app.dependency_overrides = {}
