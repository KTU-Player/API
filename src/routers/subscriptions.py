from datetime import datetime, timezone

import isodate
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas
from ..database import get_db_session
from ..dependencies import get_current_free_user
from ..services.payment_service import mock_bank_service

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.post("/upgrade", status_code=status.HTTP_204_NO_CONTENT)
async def upgrade_subscription(
    payload: schemas.SubscriptionUpgrade,
    db: AsyncSession = Depends(get_db_session),
    current_user: models.FreeUser = Depends(get_current_free_user),
):
    """
    Upgrades a user from a Free plan to a Premium plan.
    """
    # Check if user is already premium before starting a transaction
    is_premium_check = await db.scalar(
        select(models.PremiumUser).where(
            models.PremiumUser.user_id == current_user.user_id
        )
    )
    if is_premium_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already premium."
        )

    async with db.begin_nested():
        # 1. Validation
        plan = await db.get(models.SubscriptionPlan, payload.subscription_plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
            )
        if plan.plan_name == "Free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot upgrade to the Free plan.",
            )

        # 2. Payment
        success, transaction_id = await mock_bank_service.process_payment(
            payload.card_details, plan.price
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Payment failed"
            )

        now = datetime.now(timezone.utc)

        # 3. DB Step A (Cancel Old)
        active_sub_stmt = (
            select(models.Subscription)
            .where(models.Subscription.user_id == current_user.user_id)
            .where(models.Subscription.subscription_status_id == 1)  # Active
        )
        active_sub = await db.scalar(active_sub_stmt)
        if active_sub:
            active_sub.subscription_status_id = 2  # Cancelled
            active_sub.end_date = now.date()
            db.add(active_sub)

        # 4. DB Step B (Save Card)
        # In a real app, you'd get the card brand from the payment gateway
        db_payment_method = models.PaymentMethod(
            user_id=current_user.user_id,
            payment_gateway_token=transaction_id,  # Using transaction ID as a mock token
            last_4_digits=payload.card_details.card_number[-4:],
            card_brand="Visa",  # Mocked
            expiration_date=payload.card_details.expiration_date,
            owner_name=payload.card_details.card_holder_name,
        )
        db.add(db_payment_method)
        await db.flush()

        # 5. DB Step C (New Sub)
        new_end_date = now + isodate.parse_duration(plan.billing_interval)
        db_new_sub = models.Subscription(
            user_id=current_user.user_id,
            subscription_plan_id=plan.subscription_plan_id,
            start_date=now.date(),
            end_date=new_end_date.date(),
            subscription_status_id=1,  # Active
        )
        db.add(db_new_sub)
        await db.flush()

        # 6. DB Step D (Transaction)
        db_transaction = models.Transaction(
            transaction_timestamp=now,
            amount=plan.price,
            transaction_status_id=1,  # Completed
            payment_method_id=db_payment_method.payment_method_id,
            subscription_id=db_new_sub.subscription_id,
        )
        db.add(db_transaction)

        # 7. DB Step E (Promote)
        # Use a direct insert to avoid ORM inheritance issues
        stmt = insert(models.PremiumUser).values(user_id=current_user.user_id)
        await db.execute(stmt)

    await db.commit()

    return
