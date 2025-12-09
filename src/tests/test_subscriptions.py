from datetime import date, timedelta
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select

from src.main import app
from src.services.user_service import user_service
from src.database import AsyncSessionFactory
from src.models import Subscription, SubscriptionPlan, Transaction, PremiumUser
from src.schemas.user_schema import FreeUserCreate
from src.schemas.subscription_schema import SubscriptionUpgrade, CardDetails


@pytest.fixture(scope="function", autouse=True)
async def setup_subscription_plans():
    """Create subscription plans needed for testing."""
    async with AsyncSessionFactory() as session:
        free_plan = await session.get(SubscriptionPlan, 1)
        if not free_plan:
            session.add(
                SubscriptionPlan(
                    subscription_plan_id=1,
                    plan_name="Free",
                    price=0.00,
                    billing_interval="P0D",
                )
            )

        premium_plan = await session.get(SubscriptionPlan, 2)
        if not premium_plan:
            session.add(
                SubscriptionPlan(
                    subscription_plan_id=2,
                    plan_name="Premium",
                    price=9.99,
                    billing_interval="P1M",  # 1 month
                )
            )
        await session.commit()


@pytest.mark.asyncio
async def test_upgrade_subscription_success(client: AsyncClient):
    # 1. Create a free user
    user_email = "freeuser@example.com"
    user_password = "password123"
    async with AsyncSessionFactory() as session:
        free_user = await user_service.create_free_user(
            session,
            user=FreeUserCreate(
                email=user_email,
                display_name="Free User",
                password=user_password,
                date_of_birth=date(1995, 1, 1),
            ),
        )

    # 2. Log in to get the token
    login_response = await client.post(
        "/auth/token",
        data={"username": user_email, "password": user_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    access_token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 3. Prepare payload
    card_details = CardDetails(
        card_number="1234567812345678",
        expiration_date=date.today() + timedelta(days=365),
        cvv="123",
        card_holder_name="Test User",
    )
    upgrade_payload = SubscriptionUpgrade(
        subscription_plan_id=2, card_details=card_details
    )

    # 4. Call the upgrade endpoint
    response = await client.post(
        "/subscriptions/upgrade",
        json=upgrade_payload.model_dump(mode="json"),
        headers=headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # 5. Verify user is now a premium user
    async with AsyncSessionFactory() as session:
        db_user = await session.get(PremiumUser, free_user.user_id)
        assert db_user is not None

        # 6. Verify subscription and transaction
        new_sub = await session.scalar(
            select(Subscription)
            .where(Subscription.user_id == free_user.user_id)
            .where(Subscription.subscription_plan_id == 2)
            .where(Subscription.subscription_status_id == 1)
        )
        assert new_sub is not None

        transaction = await session.scalar(
            select(Transaction).where(
                Transaction.subscription_id == new_sub.subscription_id
            )
        )
        assert transaction is not None
        assert transaction.amount == 9.99
