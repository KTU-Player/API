import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_create_free_user(client: AsyncClient):
    response = await client.post(
        "/users/free",
        json={
            "email": "testuser@example.com",
            "display_name": "Test User",
            "password": "password123",
            "date_of_birth": "1990-01-01",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert "password_hash" not in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_create_free_user_duplicate_email(client: AsyncClient):
    # First user
    await client.post(
        "/users/free",
        json={
            "email": "duplicate@example.com",
            "display_name": "Test User",
            "password": "password123",
            "date_of_birth": "1990-01-01",
        },
    )
    # Second user with same email
    response = await client.post(
        "/users/free",
        json={
            "email": "duplicate@example.com",
            "display_name": "Another User",
            "password": "password456",
            "date_of_birth": "1995-05-05",
        },
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient):
    response = await client.post(
        "/users/free",
        json={
            "email": "getme@example.com",
            "display_name": "Get Me",
            "password": "password123",
            "date_of_birth": "1990-01-01",
        },
    )
    user_id = response.json()["user_id"]

    response = await client.get(f"/users/{user_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["user_id"] == user_id
    assert data["email"] == "getme@example.com"
