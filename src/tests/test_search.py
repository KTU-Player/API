from datetime import date
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select, func
from src.main import app
from src.dependencies import get_current_active_user
from src.models.user import BaseUser, Artist
from src.models.track import Track
from src.models.activity import SearchEvent
from src.database import AsyncSessionFactory


# Sample users to be returned by dependency overrides
test_active_user = BaseUser(
    user_id=1,
    email="active@test.com",
    display_name="Test Active User",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(1990, 1, 1),
)

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


async def override_get_current_active_user():
    return test_active_user


async def _create_test_track(db_session: AsyncSession, title: str, artist_id: int):
    """Helper to create a track for testing purposes."""
    new_track = Track(
        title=title,
        is_explicit=False,
        audio_key=f"test/audio/{title.replace(' ', '_')}.mp3",
        cover_key=f"test/cover/{title.replace(' ', '_')}.jpg",
        artist_id=artist_id,
        duration_ms=1000,
    )
    db_session.add(new_track)
    await db_session.commit()
    await db_session.refresh(new_track)
    return new_track


@pytest.fixture(autouse=True, scope="function")
async def setup_users_and_tracks_for_deps():
    """
    Ensures the users our dependency mocks rely on exist in the test DB
    and creates some test tracks.
    """
    async with AsyncSessionFactory() as session:
        await session.merge(test_active_user)
        await session.merge(test_artist_user)
        await _create_test_track(session, "Song One", test_artist_user.user_id)
        await _create_test_track(session, "Another Song", test_artist_user.user_id)
        await _create_test_track(session, "third song", test_artist_user.user_id)
        await _create_test_track(session, "A Different Tune", test_artist_user.user_id)
        await session.commit()


@pytest.mark.asyncio
async def test_search_tracks_success(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    async with AsyncSessionFactory() as session:
        initial_search_event_count = await session.scalar(
            select(func.count(SearchEvent.event_id))
        )

    response = await client.get("/search?q=song")

    assert response.status_code == status.HTTP_200_OK
    tracks = response.json()
    assert len(tracks) == 2  # "Song One", "Another Song", "third song" (case-insensitive)

    assert any(track["title"] == "Song One" for track in tracks)
    assert any(track["title"] == "Another Song" for track in tracks)
    assert any(track["title"] == "third song" for track in tracks)

    async with AsyncSessionFactory() as session:
        final_search_event_count = await session.scalar(
            select(func.count(SearchEvent.event_id))
        )
        assert final_search_event_count == initial_search_event_count + 1

        search_event = await session.scalar(
            select(SearchEvent)
            .filter(SearchEvent.user_id == test_active_user.user_id)
            .order_by(SearchEvent.event_id.desc())
        )
        assert search_event is not None
        assert search_event.query == "song"
        assert search_event.user_id == test_active_user.user_id

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_search_tracks_case_insensitive(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    response = await client.get("/search?q=SONG")

    assert response.status_code == status.HTTP_200_OK
    tracks = response.json()
    assert len(tracks) == 2
    assert any(track["title"] == "Song One" for track in tracks)
    assert any(track["title"] == "Another Song" for track in tracks)
    assert any(track["title"] == "third song" for track in tracks)

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_search_tracks_no_results(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    response = await client.get("/search?q=nonexistent")

    assert response.status_code == status.HTTP_200_OK
    tracks = response.json()
    assert len(tracks) == 0

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_search_tracks_pagination(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    response_page1 = await client.get("/search?q=song&limit=1&skip=0")
    assert response_page1.status_code == status.HTTP_200_OK
    tracks_page1 = response_page1.json()
    assert len(tracks_page1) == 1

    response_page2 = await client.get("/search?q=song&limit=1&skip=1")
    assert response_page2.status_code == status.HTTP_200_OK
    tracks_page2 = response_page2.json()
    assert len(tracks_page2) == 1

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_search_tracks_unauthenticated_fails(client: AsyncClient):
    # No dependency override means no authenticated user
    response = await client.get("/search?q=song")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED