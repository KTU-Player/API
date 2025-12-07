from fastapi import Depends, HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db_session
from .models.user import BaseUser, Artist, PremiumUser


async def get_current_user(
    user_id: int, db: AsyncSession = Depends(get_db_session)
) -> BaseUser:
    result = await db.execute(select(BaseUser).filter(BaseUser.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    db: AsyncSession = Depends(get_db_session),
) -> BaseUser:
    """
    Placeholder dependency to get the current authenticated user (any type).
    For demonstration, this is hardcoded to user_id=1.
    In a real app, this would be derived from an auth token.
    """
    user = await get_current_user(user_id=1, db=db)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return user


async def get_current_artist(db: AsyncSession = Depends(get_db_session)) -> Artist:
    """
    Returns the ORM object for user_id=3 (The Rockers).
    This is required for uploading/editing tracks.
    """
    result = await db.execute(select(Artist).filter(Artist.user_id == 3))
    artist = result.scalar_one_or_none()
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an artist",
        )
    return artist


async def get_current_premium_user(
    db: AsyncSession = Depends(get_db_session),
) -> PremiumUser:
    """
    Returns the ORM object for user_id=1 (Alice).
    This is required for streaming and queue interactions.
    """
    result = await db.execute(select(PremiumUser).filter(PremiumUser.user_id == 1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not a premium user"
        )
    return user


async def empty_string_to_none(file: UploadFile | None = None) -> UploadFile | None:
    """
    A dependency that converts an empty UploadFile (which comes in as an empty string
    from form data) into None. This is useful for optional file uploads.
    """
    if not file or not file.filename:
        return None
    return file
