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
        hashed_password = PasswordHasher.get_password_hash(user.password)
        db_user = models.FreeUser(
            email=user.email,
            display_name=user.display_name,
            password_hash=hashed_password,
            date_of_birth=user.date_of_birth,
            is_active=True,  # Or based on email verification in a real app
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        return db_user

    async def create_artist(
        self, db: AsyncSession, artist: schemas.ArtistCreate
    ) -> models.Artist:
        hashed_password = PasswordHasher.get_password_hash(artist.password)
        db_artist = models.Artist(
            email=artist.email,
            display_name=artist.display_name,
            password_hash=hashed_password,
            biography=artist.biography,
            social_media_link=artist.social_media_link,
            country_id=artist.country_id,
            is_active=True,
        )
        db.add(db_artist)
        await db.commit()
        await db.refresh(db_artist)
        return db_artist


user_service = UserService()
