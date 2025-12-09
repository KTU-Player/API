from datetime import date
import pytest
from httpx import AsyncClient
from fastapi import status

from src.main import app
from src.schemas.user_schema import FreeUserCreate
from src.services.user_service import user_service
from src.database import AsyncSessionFactory



@pytest.mark.asyncio
async def test_login_for_access_token(client: AsyncClient):
    # Create a user first
    user_email = "login@example.com"
    user_password = "password123"
    async with AsyncSessionFactory() as session:
        await user_service.create_free_user(
            session,
            user=FreeUserCreate(
                email=user_email,
                display_name="Login User",
                password=user_password,
                date_of_birth=date(1990, 1, 1),
            ),
        )

    # Attempt to login
    response = await client.post(
        "/auth/token",
        data={"username": user_email, "password": user_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_incorrect_password(client: AsyncClient):
    # Create a user first
    user_email = "wrongpass@example.com"
    user_password = "password123"
    async with AsyncSessionFactory() as session:
        await user_service.create_free_user(
            session,
            user=FreeUserCreate(
                email=user_email,
                display_name="Wrong Pass User",
                password=user_password,
                date_of_birth=date(1990, 1, 1),
            ),
        )

    # Attempt to login with incorrect password
    response = await client.post(
        "/auth/token",
        data={"username": user_email, "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/auth/token",
        data={"username": "nosuchuser@example.com", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_deactivate_user_account(client: AsyncClient):
    # Create a user first
    user_email = "deactivate@example.com"
    user_password = "password123"
    async with AsyncSessionFactory() as session:
        user_to_deactivate = await user_service.create_free_user(
            session,
            user=FreeUserCreate(
                email=user_email,
                display_name="Deactivate User",
                password=user_password,
                date_of_birth=date(1990, 1, 1),
            ),
        )

    # Log in to get the token
    login_response = await client.post(
        "/auth/token",
        data={"username": user_email, "password": user_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Deactivate the account
    deactivate_response = await client.delete("/users/me", headers=headers)
    assert deactivate_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify user is inactive
    async with AsyncSessionFactory() as session:
        db_user = await user_service.get_user_by_id(session, user_to_deactivate.user_id)
        assert db_user.is_active is False

    # Verify user cannot log in again
    final_login_response = await client.post(
        "/auth/token",
        data={"username": user_email, "password": user_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert final_login_response.status_code == status.HTTP_401_UNAUTHORIZED

