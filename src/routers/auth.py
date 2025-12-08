from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .. import models, schemas
from ..database import get_db_session
from ..security import PasswordHasher, create_access_token
from ..services.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user: schemas.FreeUserCreate, db: AsyncSession = Depends(get_db_session)
):
    """
    Handles user registration.
    Args:
        user: The user data for registration.
        db: The database session.
    Returns:
        A dictionary with a success message.
    """
    db_user = await user_service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # The create_free_user service handles password hashing
    await user_service.create_free_user(db=db, user=user)
    return {"msg": "User created"}


@router.post(
    "/register/artist",
    status_code=status.HTTP_201_CREATED,
)
async def register_artist(
    artist: schemas.ArtistCreate, db: AsyncSession = Depends(get_db_session)
):
    """
    Handles artist registration.
    Args:
        artist: The artist data for registration.
        db: The database session.
    Returns:
        The created artist.
    """
    db_user = await user_service.get_user_by_email(db, email=artist.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    await user_service.create_artist(db=db, artist=artist)
    return {"msg": "Artist created"}


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db_session),
):
    """
    Handles user login and returns an access token.
    Args:
        form_data: The form data with username (email) and password.
        db: The database session.
    Returns:
        A dictionary with the access token and token type.
    """
    user = await user_service.get_user_by_email(db, email=form_data.username)
    if (
        not user
        or not user.is_active
        or not PasswordHasher.verify_password(form_data.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login timestamp
    user.last_login_date = datetime.now(timezone.utc)
    await db.commit()

    # Determine role
    # The order of checks is important. An artist can also be a premium user,
    # but 'artist' is a more specific role for content creation.
    role = "free"
    is_artist = await db.scalar(
        select(models.Artist).where(models.Artist.user_id == user.user_id)
    )
    is_premium = await db.scalar(
        select(models.PremiumUser).where(models.PremiumUser.user_id == user.user_id)
    )
    if is_artist:
        role = "artist"
    elif is_premium:
        role = "premium"
    access_token = create_access_token(data={"sub": str(user.user_id), "role": role})
    return {"access_token": access_token, "token_type": "bearer"}
