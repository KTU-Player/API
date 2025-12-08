from datetime import date, datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select, func
from src.main import app
from src.dependencies import get_current_artist
from src.models.user import Artist, FreeUser
from src.models.track import Track
from src.models.activity import UserActivityEvent, StreamEvent
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

test_other_artist_user = Artist(
    user_id=4,
    email="other_artist@test.com",
    display_name="Other Artist",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    biography="Another test artist",
    date_of_birth=date(1990, 1, 1),
    social_media_link="https://otherartist.com",
    country_id=1,
)


test_free_user_1 = FreeUser(
    user_id=1,
    email="freeuser1@test.com",
    display_name="Free User 1",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(2000, 1, 1),
)

test_free_user_2 = FreeUser(
    user_id=2,
    email="freeuser2@test.com",
    display_name="Free User 2",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(2001, 1, 1),
)


async def override_get_current_artist():
    return test_artist_user


async def _create_test_track(db_session: AsyncSession, title: str, artist_id: int):
    """Helper to create a track for testing purposes."""
    new_track = Track(
        title=title,
        is_explicit=False,
        audio_key=f"test/audio/{title.replace(' ', '_')}.mp3",
        cover_key=f"test/cover/{title.replace(' ', '_')}.jpg",
        release_date=date.today(),
        artist_id=artist_id,
        duration_ms=60000,
    )
    db_session.add(new_track)
    await db_session.commit()
    await db_session.refresh(new_track)
    return new_track


async def _create_stream_event(
    db_session: AsyncSession, user_id: int, track_id: int, duration_ms: int, timestamp: datetime
):
    """Helper to create a stream event for testing purposes."""
    user_activity_event = UserActivityEvent(
        event_timestamp=timestamp, user_id=user_id
    )
    db_session.add(user_activity_event)
    await db_session.flush()

    stream_event = StreamEvent(
        event_id=user_activity_event.event_id,
        duration_milliseconds=duration_ms,
        was_skipped=False,
        track_id=track_id,
    )
    db_session.add(stream_event)
    await db_session.commit()


@pytest.fixture(autouse=True, scope="function")
async def setup_data_for_analytics():
    """
    Sets up users, artists, tracks, and stream events for analytics tests.
    """
    async with AsyncSessionFactory() as session:
        # Add users
        await session.merge(test_artist_user)
        await session.merge(test_other_artist_user)
        await session.merge(test_free_user_1)
        await session.merge(test_free_user_2)
        await session.commit()

        # Create tracks
        track1 = await _create_test_track(session, "Artist Track 1", test_artist_user.user_id)
        track2 = await _create_test_track(session, "Artist Track 2", test_artist_user.user_id)
        other_artist_track = await _create_test_track(session, "Other Artist Track", test_other_artist_user.user_id)

        # Create stream events for test_artist_user's tracks
        # Total streams: 4 (3 for track1, 1 for track2)
        # Monthly listeners: 2 (free_user_1, free_user_2)
        # Top track: Artist Track 1
        # Avg duration: track1: 60s, track2: 60s

        # Stream events within last 30 days
        await _create_stream_event(session, test_free_user_1.user_id, track1.track_id, 60000, datetime.now(timezone.utc) - timedelta(days=5))
        await _create_stream_event(session, test_free_user_1.user_id, track1.track_id, 60000, datetime.now(timezone.utc) - timedelta(days=10))
        await _create_stream_event(session, test_free_user_2.user_id, track1.track_id, 60000, datetime.now(timezone.utc) - timedelta(days=15))
        await _create_stream_event(session, test_free_user_1.user_id, track2.track_id, 60000, datetime.now(timezone.utc) - timedelta(days=20))

        # Stream event older than 30 days (should not count for monthly listeners)
        await _create_stream_event(session, test_free_user_1.user_id, track1.track_id, 50000, datetime.now(timezone.utc) - timedelta(days=35))
        # Stream event for other artist (should not count for current artist)
        await _create_stream_event(session, test_free_user_1.user_id, other_artist_track.track_id, 70000, datetime.now(timezone.utc) - timedelta(days=5))

        await session.commit()


@pytest.mark.asyncio
async def test_get_artist_dashboard_analytics_success(client: AsyncClient):
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    response = await client.get("/analytics/dashboard")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["monthly_listeners"] == 2
    assert data["total_streams"] == 4
    assert data["top_track"] == "Artist Track 1"
    assert len(data["avg_duration_per_track"]) == 2
    assert {"track_title": "Artist Track 1", "avg_seconds": 60.0} in data["avg_duration_per_track"]
    assert {"track_title": "Artist Track 2", "avg_seconds": 60.0} in data["avg_duration_per_track"]

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_artist_dashboard_analytics_no_tracks(client: AsyncClient):
    # Override get_current_artist to return an artist with no tracks
    no_track_artist = Artist(
        user_id=99,
        email="notracks@test.com",
        display_name="No Tracks Artist",
        password_hash="hashed_password",
        last_login_date=date.today(),
        is_active=True,
        biography="An artist with no tracks",
        date_of_birth=date(1980, 1, 1),
        social_media_link="https://notracks.com",
        country_id=1,
    )

    async def override_get_current_no_track_artist():
        return no_track_artist

    app.dependency_overrides[get_current_artist] = override_get_current_no_track_artist

    async with AsyncSessionFactory() as session:
        await session.merge(no_track_artist)
        await session.commit()

    response = await client.get("/analytics/dashboard")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["monthly_listeners"] == 0
    assert data["total_streams"] == 0
    assert data["top_track"] is None
    assert data["avg_duration_per_track"] == []

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_artist_dashboard_analytics_unauthenticated_fails(client: AsyncClient):
    # No dependency override means no authenticated artist
    app.dependency_overrides[get_current_artist] = None # Simulate no artist logged in
    response = await client.get("/analytics/dashboard")
    assert response.status_code == status.HTTP_403_FORBIDDEN # get_current_artist raises 403

    app.dependency_overrides = {}
