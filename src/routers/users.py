from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..database import get_db_session
from ..services.user_service import user_service
from ..models import Country, BaseUser
from ..dependencies import get_current_active_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/free", response_model=schemas.FreeUserInDB, status_code=status.HTTP_201_CREATED
)
async def create_free_user(
    user_in: schemas.FreeUserCreate, db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new free user.
    """
    db_user = await user_service.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return await user_service.create_free_user(db=db, user=user_in)


@router.post(
    "/artist", response_model=schemas.ArtistInDB, status_code=status.HTTP_201_CREATED
)
async def create_artist(
    artist_in: schemas.ArtistCreate, db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new artist.
    """
    db_user = await user_service.get_user_by_email(db, email=artist_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # Verify that the country ID exists
    country = await db.get(Country, artist_in.country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Country with id {artist_in.country_id} not found",
        )
    return await user_service.create_artist(db=db, artist=artist_in)


@router.get("/{user_id}", response_model=schemas.User)
async def read_user(user_id: int, db: AsyncSession = Depends(get_db_session)):
    """
    Get a user by their ID.
    """
    db_user = await user_service.get_user_by_id(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return db_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: BaseUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Deactivate the current user's account (soft delete for GDPR compliance).
    """
    # The user is already fetched by the dependency.
    # We can now mark them as inactive.
    current_user.is_active = False
    db.add(current_user)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
