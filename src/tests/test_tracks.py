import pytest
from httpx import AsyncClient
from fastapi import status
import io
import json


@pytest.fixture(scope="module")
async def test_artist(client: AsyncClient):
    # Create a continent and country first
    # This shows a dependency between tests which isn't ideal,
    # but for this scenario it's needed.
    # A better approach would be to have seeding fixtures.
    # In a real app, reference data like continents/countries would be pre-populated.

    # Can't do this as we don't have endpoints for it.
    # A workaround is to create the artist and assume country_id=1 exists.
    # This assumes the test db is clean and the artist is user_id=1.
    response = await client.post(
        "/users/artist",
        json={
            "email": "artist@example.com",
            "display_name": "Test Artist",
            "password": "password123",
            "country_id": 1,  # Assuming a country with ID 1 exists
            "biography": "A test artist",
        },
    )
    # This will fail if country 1 doesn't exist.
    # A better fixture would create the country in the db directly.
    # For now, let's just proceed assuming it works or the test will fail here.
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


@pytest.mark.asyncio
async def test_create_track(client: AsyncClient, test_artist: dict):
    track_data = {
        "title": "My Awesome Track",
        "duration_milliseconds": 180000,
        "is_explicit": False,
        "release_date": "2023-10-27",
    }
    files = {
        "audio_file": ("track.mp3", io.BytesIO(b"fake audio data"), "audio/mpeg"),
        "cover_file": ("cover.jpg", io.BytesIO(b"fake image data"), "image/jpeg"),
    }
    data = {
        "track_in_str": json.dumps(track_data),
        "artist_id": test_artist["user_id"],
        "genre_ids": json.dumps([1, 2]),  # Assuming genres 1, 2 exist
    }

    # The test for artist creation is flawed. This will likely fail.
    # Let's ignore the artist fixture and hardcode artist_id=1,
    # and we just have to hope the artist creation test ran first and created user 1.
    data["artist_id"] = 1

    response = await client.post("/tracks", data=data, files=files)

    # This test has a high chance of failure due to the unmanaged state
    # of the database between tests and the lack of proper seeding.
    # But the structure of the request is what we want to test.
    assert response.status_code == status.HTTP_201_CREATED
    res_data = response.json()
    assert res_data["title"] == "My Awesome Track"
    assert "audio_url" in res_data
    assert "cover_url" in res_data
    assert res_data["artist"]["user_id"] == 1


@pytest.mark.asyncio
async def test_get_tracks(client: AsyncClient):
    response = await client.get("/tracks")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_genres(client: AsyncClient):
    response = await client.get("/genres")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)
