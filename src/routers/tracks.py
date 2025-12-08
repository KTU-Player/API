from datetime import datetime, timezone
from minio.error import S3Error
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    status,
    Request,
    Response,
)
from pydantic import BaseModel, HttpUrl
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import selectinload

from src.database import get_db_session
from src.dependencies import (
    get_current_artist,
    get_current_premium_user,
    get_current_user,
    get_current_free_user,
    get_genre_ids,
)
from src.models.location import Country
from src.models.user import PremiumUser, FreeUser, Artist, BaseUser
from src.models.track import Track
from src.models.activity import StreamEvent
from src.models.queue import Queue, QueueItem
from src.schemas.track_schema import TrackCreate, TrackUpdate, Track as TrackSchema
from src.services.track_service import track_service
from src.services.storage_service import storage_service

router = APIRouter(prefix="/tracks", tags=["tracks"])


class StreamUrlResponse(BaseModel):
    url: HttpUrl


class CoverImageUrlResponse(BaseModel):
    url: HttpUrl


class TrackPlayLog(BaseModel):
    duration_milliseconds: int
    was_skipped: bool


class TrackPreviewUrl(BaseModel):
    url: HttpUrl
    preview_duration_seconds: int


@router.post("", response_model=TrackSchema, status_code=status.HTTP_201_CREATED)
async def create_track(
    track_in: TrackCreate = Depends(),
    genre_ids: list[int] = Depends(get_genre_ids),
    audio_file: UploadFile = File(...),
    cover_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    """
    Creates a new track.
    """
    if not genre_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one genre must be selected.",
        )
    new_track = await track_service.create_track(
        db,
        track_in,
        current_artist.user_id,
        genre_ids,
        audio_file,
        cover_file,
    )

    result = await db.execute(
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(Track.track_id == new_track.track_id)
    )
    return result.scalar_one()


@router.get("/my-tracks", response_model=list[TrackSchema])
async def get_my_tracks(
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
    skip: int = 0,
    limit: int = 100,
):
    """
    Returns all tracks for the current artist.
    """
    tracks = await track_service.get_all_tracks_by_artist(
        db, artist_id=current_artist.user_id, skip=skip, limit=limit
    )
    return tracks


@router.post("/{track_id}/log-play", status_code=status.HTTP_204_NO_CONTENT)
async def log_track_play(
    track_id: int,
    play_log: TrackPlayLog,
    db: AsyncSession = Depends(get_db_session),
    current_user: FreeUser = Depends(get_current_free_user),
):
    """
    Logs a track play event (beacon).
    """
    result = await db.execute(select(Track).filter(Track.track_id == track_id))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Create StreamEvent, letting SQLAlchemy handle the UserActivityEvent creation
    stream_event = StreamEvent(
        event_timestamp=datetime.now(timezone.utc),
        user_id=current_user.user_id,
        duration_milliseconds=play_log.duration_milliseconds,
        was_skipped=play_log.was_skipped,
        track_id=track_id,
    )
    db.add(stream_event)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{track_id}/preview-audio")
async def preview_track_audio(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: FreeUser = Depends(get_current_free_user),  # Any authenticated user
):
    """
    Provides a secure audio preview (first 1MB) for a track.
    """
    track = await track_service.get_track_by_id(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    preview_limit_bytes = 1024 * 1024  # 1 MB
    bucket_name = storage_service.audio_bucket
    object_name = track.audio_key

    try:
        # Check if the object exists and get its size
        stat = storage_service.client.stat_object(bucket_name, object_name)
        file_size = stat.size
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")

    if file_size is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Determine the actual length to retrieve
    length_to_retrieve = min(file_size, preview_limit_bytes)

    def file_iterator(bucket, obj, length):
        with storage_service.client.get_object(bucket, obj, length=length) as response:
            yield from response

    return StreamingResponse(
        file_iterator(bucket_name, object_name, length_to_retrieve),
        media_type="audio/mpeg",
        headers={"Content-Length": str(length_to_retrieve)},
    )


@router.get("/{track_id}/preview-url", response_model=TrackPreviewUrl)
async def get_track_preview_url(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: FreeUser = Depends(get_current_free_user),  # Any authenticated user
):
    """
    Provides an insecure presigned URL for a track preview,
    relying on the frontend to limit playback.
    """
    track = await track_service.get_track_by_id(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    url = storage_service.get_presigned_url(
        track.audio_key, storage_service.audio_bucket
    )
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate preview URL.")

    return TrackPreviewUrl(url=HttpUrl(url), preview_duration_seconds=30)


@router.get("/{track_id}/cover-url", response_model=CoverImageUrlResponse)
async def get_track_cover_url(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: BaseUser = Depends(get_current_user),  # Any authenticated user
):
    """
    Generates a pre-signed URL for a track's cover image.
    """
    track = await track_service.get_track_by_id(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    url = storage_service.get_presigned_url(
        track.cover_key, storage_service.covers_bucket
    )
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate cover URL.")

    return CoverImageUrlResponse(url=HttpUrl(url))


@router.get("/{track_id}/cover-image")
async def get_track_cover_image(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: BaseUser = Depends(get_current_user),  # Any authenticated user
):
    """
    Streams a track's cover image directly.
    """
    track = await track_service.get_track_by_id(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    bucket_name = storage_service.covers_bucket
    object_name = track.cover_key

    try:
        stat = storage_service.client.stat_object(bucket_name, object_name)
        file_size = stat.size
    except S3Error:
        raise HTTPException(status_code=404, detail="Cover image file not found")

    if file_size is None:
        raise HTTPException(status_code=404, detail="Cover image file not found")

    def file_iterator(bucket, obj):
        with storage_service.client.get_object(bucket, obj) as response:
            yield from response

    # Assuming cover images are JPEGs. You might want to store the content type
    # in your database alongside the track for more accuracy.
    return StreamingResponse(
        file_iterator(bucket_name, object_name),
        media_type="image/jpeg",
        headers={"Content-Length": str(file_size)},
    )


@router.get("/{track_id}", response_model=TrackSchema)
async def get_track_by_id(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: BaseUser = Depends(get_current_user),  # Any authenticated user
):
    """
    Returns a track by its ID.
    """
    track = await track_service.get_track_by_id(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


@router.put("/{track_id}", response_model=TrackSchema)
async def update_track(
    track_id: int,
    track_in: TrackUpdate = Depends(),
    genre_ids: list[int] | None = Depends(get_genre_ids),
    cover_file: UploadFile | None = None,
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    if genre_ids is not None and not genre_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one genre must be selected.",
        )
    updated_track = await track_service.update_track(
        db, track_id, track_in, current_artist.user_id, cover_file, genre_ids
    )
    if not updated_track:
        raise HTTPException(status_code=404, detail="Track not found")

    result = await db.execute(
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(Track.track_id == updated_track.track_id)
    )
    return result.scalar_one()


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_track(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    result = await db.execute(select(Track).filter(Track.track_id == track_id))
    track = result.scalar_one_or_none()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if track.artist_id != current_artist.user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this track"
        )

    storage_service.delete_file(track.audio_key, storage_service.audio_bucket)
    storage_service.delete_file(track.cover_key, storage_service.covers_bucket)

    track.is_active = False
    db.add(track)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{track_id}/stream-audio")
async def stream_track(
    track_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: PremiumUser = Depends(get_current_premium_user),
):
    result = await db.execute(
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(Track.track_id == track_id, Track.is_active.is_(True))
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    bucket_name = storage_service.audio_bucket
    object_name = track.audio_key

    try:
        stat = storage_service.client.stat_object(bucket_name, object_name)
        file_size = stat.size
    except S3Error as e:
        raise HTTPException(status_code=404, detail=f"Audio file not found: {e}")

    if file_size is None:
        raise HTTPException(status_code=404, detail="Audio file not found")

    range_header = request.headers.get("Range")
    start = 0
    end = file_size - 1
    status_code = 200

    headers = {
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
        "Content-Type": "audio/mpeg",  # Adjust based on actual content type
    }

    if range_header:
        range_str = range_header.replace("bytes=", "")
        parts = range_str.split("-")
        start = int(parts[0])
        if len(parts) > 1 and parts[1]:
            end = int(parts[1])
        else:
            end = file_size - 1

        if start >= file_size or end >= file_size:
            raise HTTPException(
                status_code=416, detail="Requested Range Not Satisfiable"
            )

        chunk_size = (end - start) + 1
        headers["Content-Length"] = str(chunk_size)
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206

    def file_iterator(bucket, obj, start_byte, end_byte):
        with storage_service.client.get_object(
            bucket, obj, offset=start_byte, length=(end_byte - start_byte) + 1
        ) as response:
            yield from response

    return StreamingResponse(
        file_iterator(bucket_name, object_name, start, end),
        status_code=status_code,
        headers=headers,
        media_type="audio/mpeg",
    )


@router.get("/{track_id}/stream-url", response_model=StreamUrlResponse)
async def get_track_stream_url(
    track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: PremiumUser = Depends(get_current_premium_user),
):
    """
    Generates a pre-signed URL for streaming a track's audio file.
    """
    result = await db.execute(
        select(Track).filter(Track.track_id == track_id, Track.is_active.is_(True))
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    url = storage_service.get_presigned_url(
        track.audio_key, storage_service.audio_bucket
    )
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate stream URL.")

    return StreamUrlResponse(url=HttpUrl(url))


@router.post("/{seed_track_id}/recommendations", response_model=list[TrackSchema])
async def get_recommendations(
    seed_track_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: PremiumUser = Depends(get_current_premium_user),
):
    result = await db.execute(select(Track).filter(Track.track_id == seed_track_id))
    seed_track = result.scalar_one_or_none()
    if not seed_track:
        raise HTTPException(status_code=404, detail="Seed track not found")

    result = await db.execute(
        select(Queue)
        .options(selectinload(Queue.items).selectinload(QueueItem.track))
        .filter(Queue.user_id == current_user.user_id)
    )
    user_queue = result.scalar_one_or_none()

    if not user_queue:
        user_queue = Queue(user_id=current_user.user_id)
        db.add(user_queue)
        await db.flush()  # Flush to get the new queue_id
        await db.refresh(user_queue, attribute_names=["items"])  # Eagerly load items

    current_track_ids_in_queue = [item.track_id for item in user_queue.items]

    result = await db.execute(
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(
            and_(
                Track.track_id != seed_track_id,
                ~Track.track_id.in_(current_track_ids_in_queue),
                Track.is_active.is_(True),
            )
        )
        .order_by(func.random())
        .limit(3)
    )
    recommendations = result.scalars().all()

    if not recommendations:
        raise HTTPException(status_code=404, detail="No recommendations found")

    result = await db.execute(
        select(func.max(QueueItem.position_order)).filter(
            QueueItem.queue_id == user_queue.queue_id
        )
    )
    max_pos = result.scalar() or 0

    new_queue_items = []
    for i, track in enumerate(recommendations):
        new_item = QueueItem(
            queue_id=user_queue.queue_id,
            track_id=track.track_id,
            position_order=max_pos + i + 1,
        )
        new_queue_items.append(new_item)

    db.add_all(new_queue_items)
    await db.commit()

    return recommendations
