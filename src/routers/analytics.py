from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.dependencies import get_current_artist
from src.models.user import Artist
from src.models.track import Track
from src.models.activity import UserActivityEvent, StreamEvent
from src.schemas.analytics_schema import ArtistAnalytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=ArtistAnalytics)
async def get_artist_dashboard_analytics(
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    """
    Retrieves analytics data for the current artist's tracks.
    """
    artist_track_ids_query = select(Track.track_id).filter(
        Track.artist_id == current_artist.user_id
    )
    artist_track_ids_result = await db.execute(artist_track_ids_query)
    artist_track_ids = artist_track_ids_result.scalars().all()

    if not artist_track_ids:
        return ArtistAnalytics(
            monthly_listeners=0,
            total_streams=0,
            top_track=None,
            avg_duration_per_track=[],
        )

    # Metric A: Monthly Listeners (Unique users in the last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    monthly_listeners_query = (
        select(func.count(func.distinct(UserActivityEvent.user_id)))
        .join(StreamEvent, StreamEvent.event_id == UserActivityEvent.event_id)
        .filter(
            StreamEvent.track_id.in_(artist_track_ids),
            UserActivityEvent.event_timestamp >= thirty_days_ago,
        )
    )
    monthly_listeners = (await db.execute(monthly_listeners_query)).scalar_one()

    # Metric B: Total Streams (All time)
    total_streams_query = select(func.count(StreamEvent.event_id)).filter(
        StreamEvent.track_id.in_(artist_track_ids)
    )
    total_streams = (await db.execute(total_streams_query)).scalar_one()

    # Metric C: Most Streamed Track
    most_streamed_track_query = (
        select(Track.title)
        .join(StreamEvent, StreamEvent.track_id == Track.track_id)
        .filter(StreamEvent.track_id.in_(artist_track_ids))
        .group_by(Track.track_id, Track.title)
        .order_by(desc(func.count(StreamEvent.event_id)))
        .limit(1)
    )
    top_track = (await db.execute(most_streamed_track_query)).scalar_one_or_none()

    # Metric D: Average Stream Duration (Bar Chart Data)
    avg_duration_query = (
        select(
            Track.title,
            (func.avg(StreamEvent.duration_milliseconds) / 1000.0).label("avg_seconds"),
        )
        .join(StreamEvent, StreamEvent.track_id == Track.track_id)
        .filter(StreamEvent.track_id.in_(artist_track_ids))
        .group_by(Track.title)
        .order_by(desc(func.avg(StreamEvent.duration_milliseconds)))
    )
    avg_duration_results = (await db.execute(avg_duration_query)).fetchall()
    avg_duration_per_track = [
        {"track_title": title, "avg_seconds": round(avg_sec, 2)}
        for title, avg_sec in avg_duration_results
    ]

    return ArtistAnalytics(
        monthly_listeners=monthly_listeners,
        total_streams=total_streams,
        top_track=top_track,
        avg_duration_per_track=avg_duration_per_track,
    )
