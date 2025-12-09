from datetime import date
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select

from src.main import app
from src.services.user_service import user_service
from src.database import AsyncSessionFactory
from src.models import (
    Track,
    Artist,
    PremiumUser,
    Queue,
    QueueItem,
    SubscriptionPlan,
    Genre,
)
from src.schemas.user_schema import FreeUserCreate, ArtistCreate
from src.dependencies import get_current_premium_user, get_current_artist


test_premium_user_model = PremiumUser(
    user_id=1,
    email="premium@test.com",
    display_name="Test Premium",
    password_hash="hashed_password",
    last_login_date=date.today(),
    is_active=True,
    date_of_birth=date(1995, 5, 10),
)

test_artist_user_model = Artist(
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


async def override_get_current_premium_user():
    return test_premium_user_model


async def override_get_current_artist():
    return test_artist_user_model


async def _create_test_track(session, artist_id):
    """Helper to create a track for testing purposes."""
    new_track = Track(
        title="Test Track",
        is_explicit=False,
        audio_key="test/audio/key.mp3",
        cover_key="test/cover/key.jpg",
        artist_id=artist_id,
        duration_ms=1000,
    )
    session.add(new_track)
    await session.commit()
    await session.refresh(new_track)
    return new_track


@pytest.fixture(autouse=True, scope="function")
async def setup_users_and_plans():
    """Create users and subscription plans for tests."""
    async with AsyncSessionFactory() as session:
        await session.merge(test_premium_user_model)
        await session.merge(test_artist_user_model)
        # Ensure plans exist
        if not await session.get(SubscriptionPlan, 1):
            session.add_all(
                [
                    SubscriptionPlan(
                        subscription_plan_id=1,
                        plan_name="Free",
                        price=0.0,
                        billing_interval="P0M",
                    ),
                    SubscriptionPlan(
                        subscription_plan_id=2,
                        plan_name="Premium",
                        price=9.99,
                        billing_interval="P1M",
                    ),
                ]
            )
        if not await session.get(Genre, 1):
            session.add(Genre(genre_id=1, name="Test Genre"))
        await session.commit()


@pytest.mark.asyncio
async def test_get_empty_queue(client: AsyncClient):
    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user
    response = await client.get("/queue")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["items"] == []
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_queue_with_items_after_recommendations(client: AsyncClient):
    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    async with AsyncSessionFactory() as session:
        seed_track = await _create_test_track(session, test_artist_user_model.user_id)
        await _create_test_track(session, test_artist_user_model.user_id)
        await _create_test_track(session, test_artist_user_model.user_id)
        await _create_test_track(session, test_artist_user_model.user_id)

    # Get recommendations to populate the queue
    await client.post(f"/tracks/{seed_track.track_id}/recommendations")

    response = await client.get("/queue")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data["items"]) == 3
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_remove_track_from_queue(client: AsyncClient):
    app.dependency_overrides[
        get_current_premium_user
    ] = override_get_current_premium_user
    app.dependency_overrides[get_current_artist] = override_get_current_artist

    async with AsyncSessionFactory() as session:
        seed_track = await _create_test_track(session, test_artist_user_model.user_id)
        rec_track = await _create_test_track(session, test_artist_user_model.user_id)
        await _create_test_track(session, test_artist_user_model.user_id)
        await _create_test_track(session, test_artist_user_model.user_id)
        # Manually add a track to the queue for deletion
        user_queue = Queue(user_id=test_premium_user_model.user_id)
        session.add(user_queue)
        await session.flush()
        queue_item = QueueItem(
            queue_id=user_queue.queue_id, track_id=rec_track.track_id, position_order=1
        )
        session.add(queue_item)
        await session.commit()

    # Remove the track
    response = await client.delete(f"/queue/{rec_track.track_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify track is removed
    async with AsyncSessionFactory() as session:
        item = await session.get(QueueItem, queue_item.item_id)
        assert item is None

    app.dependency_overrides = {}
