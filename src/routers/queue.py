from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database import get_db_session
from src.dependencies import get_current_premium_user
from src.models.user import PremiumUser
from src.models.track import Track
from src.models.user import Artist
from src.models.queue import Queue, QueueItem
from src.schemas.queue_schema import Queue as QueueSchema

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("", response_model=QueueSchema)
async def get_user_queue(
    db: AsyncSession = Depends(get_db_session),
    current_user: PremiumUser = Depends(get_current_premium_user),
):
    result = await db.execute(
        select(Queue)
        .options(
            selectinload(Queue.items)
            .selectinload(QueueItem.track)
            .selectinload(Track.artist)
            .selectinload(Artist.country),
            selectinload(Queue.items)
            .selectinload(QueueItem.track)
            .selectinload(Track.genres),
        )
        .filter(Queue.user_id == current_user.user_id)
    )
    user_queue = result.scalar_one_or_none()
    if not user_queue:
        # Per business logic, queues are created via recommendations,
        # but returning an empty queue for a user who hasn't generated any is fine.
        return QueueSchema(queue_id=-1, user_id=current_user.user_id, items=[])
    return user_queue


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_track_from_queue(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: PremiumUser = Depends(get_current_premium_user),
):
    result = await db.execute(
        select(Queue).filter(Queue.user_id == current_user.user_id)
    )
    user_queue = result.scalar_one_or_none()
    if not user_queue:
        raise HTTPException(status_code=404, detail="Queue not found for this user.")

    result = await db.execute(
        select(QueueItem).filter(
            QueueItem.queue_id == user_queue.queue_id,
            QueueItem.track_id == track_id,
        )
    )
    item_to_delete = result.scalar_one_or_none()

    if not item_to_delete:
        raise HTTPException(
            status_code=404, detail="Track not found in the user's queue."
        )

    await db.delete(item_to_delete)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
