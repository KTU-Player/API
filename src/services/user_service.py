from datetime import date, datetime, timezone
import isodate

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas
from ..security import PasswordHasher


class UserService:
    async def get_user_by_id(
        self, db: AsyncSession, user_id: int
    ) -> models.BaseUser | None:
        stmt = select(models.BaseUser).where(models.BaseUser.user_id == user_id)
        return await db.scalar(stmt)

    async def get_user_by_email(
        self, db: AsyncSession, email: str
    ) -> models.BaseUser | None:
        stmt = select(models.BaseUser).where(models.BaseUser.email == email)
        return await db.scalar(stmt)

    async def create_free_user(
        self, db: AsyncSession, user: schemas.FreeUserCreate
    ) -> models.FreeUser:
        hashed_password = PasswordHasher.get_password_hash(
            user.password.get_secret_value()
        )
        db_user = models.FreeUser(
            email=user.email,
            display_name=user.display_name,
            password_hash=hashed_password,
            creation_date=date.today(),
            date_of_birth=user.date_of_birth,
            last_login_date=None,
            is_active=True,  # Or based on email verification in a real app
        )
        db.add(db_user)
        await db.flush()  # Flush to get the user_id for the new user

        # Find the "Free" subscription plan
        free_plan_stmt = select(models.SubscriptionPlan).where(
            models.SubscriptionPlan.plan_name == "Free"
        )
        free_plan = await db.scalar(free_plan_stmt)
        if not free_plan:
            raise Exception("Free subscription plan not found")

        # Find the "Active" status
        active_status_stmt = select(models.SubscriptionStatus).where(
            models.SubscriptionStatus.subscription_status_name == "Active"
        )
        active_status = await db.scalar(active_status_stmt)
        if not active_status:
            raise Exception("Active subscription status not found")

        # Create an active subscription for the new user
        now = datetime.now(timezone.utc)
        end_date = now + isodate.parse_duration(free_plan.billing_interval)

        db_subscription = models.Subscription(
            user_id=db_user.user_id,
            subscription_plan_id=free_plan.subscription_plan_id,
            start_date=now.date(),
            end_date=end_date.date(),
            subscription_status_id=active_status.subscription_status_id,
        )
        db.add(db_subscription)

        db_queue = models.Queue(user_id=db_user.user_id)
        db.add(db_queue)

        await db.commit()
        await db.refresh(db_user)
        return db_user

    async def create_artist(
        self, db: AsyncSession, artist: schemas.ArtistCreate
    ) -> models.Artist:
        hashed_password = PasswordHasher.get_password_hash(
            artist.password.get_secret_value()
        )
        db_artist = models.Artist(
            email=artist.email,
            display_name=artist.display_name,
            password_hash=hashed_password,
            creation_date=date.today(),
            date_of_birth=artist.date_of_birth,
            biography=artist.biography,
            social_media_link=artist.social_media_link,
            country_id=artist.country_id,
            last_login_date=None,
            is_active=True,
        )
        db.add(db_artist)
        await db.commit()
        await db.refresh(db_artist, attribute_names=["country"])
        return db_artist


user_service = UserService()
