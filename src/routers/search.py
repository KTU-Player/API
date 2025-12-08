from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db_session
from src.dependencies import get_current_free_user
from src.models.track import Track
from src.models.user import FreeUser, Artist
from src.models.activity import SearchEvent
from src.schemas.track_schema import Track as TrackSchema
from src.models.location import Country

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[TrackSchema])
async def search_tracks(
    q: str = Query(..., min_length=1, description="Search query for track titles"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: FreeUser = Depends(get_current_free_user),
):
    """
    Searches for tracks by title and logs the search query as a UserActivityEvent.
    """
    # Log the search event
    search_event = SearchEvent(
        event_timestamp=datetime.now(timezone.utc),
        user_id=current_user.user_id,
        query=q,
    )
    db.add(search_event)
    await db.commit()

    # Perform the track search
    search_query = (
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(Track.title.ilike(f"%{q}%"), Track.is_active.is_(True))
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(search_query)
    tracks = result.scalars().all()

    return tracks
