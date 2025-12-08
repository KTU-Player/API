from typing import Annotated

from fastapi import Depends, HTTPException, status, UploadFile, Form
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List


from .config import settings
from .database import get_db_session
from .models.user import BaseUser, Artist, PremiumUser, FreeUser
from .schemas.token_schema import TokenData
from .services.user_service import user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_token_data(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id = str(payload.get("sub"))
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=int(user_id), role=payload.get("role"))
    except (JWTError, ValueError):
        raise credentials_exception
    if token_data.user_id is None:
        raise credentials_exception
    return token_data


async def get_current_user(
    token_data: Annotated[TokenData, Depends(get_token_data)],
    db: AsyncSession = Depends(get_db_session),
) -> BaseUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token_data.user_id is None:
        raise credentials_exception
    user = await user_service.get_user_by_id(db, user_id=token_data.user_id)
    if user is None:
        raise credentials_exception
    return user


async def get_current_artist(
    token_data: Annotated[TokenData, Depends(get_token_data)],
    db: AsyncSession = Depends(get_db_session),
) -> Artist:
    """
    Returns the ORM object for the current user if they are an artist.
    """
    if token_data.role != "artist":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not an artist"
        )
    artist = await db.get(Artist, token_data.user_id)
    if not artist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an artist",
        )
    return artist


async def get_current_premium_user(
    token_data: Annotated[TokenData, Depends(get_token_data)],
    db: AsyncSession = Depends(get_db_session),
) -> PremiumUser:
    """
    Returns the ORM object for the current user if they are a premium user.
    """
    if token_data.role != "premium":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not a premium user"
        )
    premium_user = await db.get(PremiumUser, token_data.user_id)
    if not premium_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not a premium user"
        )
    return premium_user


async def get_current_free_user(
    token_data: Annotated[TokenData, Depends(get_token_data)],
    db: AsyncSession = Depends(get_db_session),
) -> FreeUser:
    """
    Returns the ORM object for the current user if they are a free user.
    """
    if token_data.role not in ["free", "premium"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not a free user"
        )
    free_user = await db.get(FreeUser, token_data.user_id)
    if not free_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is not a free user"
        )
    return free_user


async def empty_string_to_none(file: UploadFile | None = None) -> UploadFile | None:
    """
    A dependency that converts an empty UploadFile (which comes in as an empty string
    from form data) into None. This is useful for optional file uploads.
    """
    if not file or not file.filename:
        return None
    return file


async def get_genre_ids(genre_ids: str = Form(...)) -> List[int]:
    """
    Parses a comma-separated string of genre IDs from form data into a list of integers.
    """
    if not genre_ids:
        return []
    try:
        return [int(gid.strip()) for gid in genre_ids.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid genre_ids format. Expected a comma-separated list of integers.",
        )
