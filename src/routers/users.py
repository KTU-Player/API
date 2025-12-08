from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..database import get_db_session
from ..services.user_service import user_service
from ..models import BaseUser
from ..dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: BaseUser = Depends(get_current_user),
):
    """
    Get the current user's profile.
    """
    return current_user


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
    current_user: BaseUser = Depends(get_current_user),
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
