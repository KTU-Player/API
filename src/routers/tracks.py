from datetime import datetime, timezone
from minio.error import S3Error
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
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
from fastapi.responses import StreamingResponse

from src.database import get_db_session
from src.dependencies import (
    get_current_artist,
    get_current_premium_user,
    empty_string_to_none,
)
from src.models.user import PremiumUser
from src.models.track import Track
from src.models.location import Country
from src.models.user import Artist
from src.models.activity import StreamEvent
from src.models.queue import Queue, QueueItem
from src.schemas.track_schema import TrackCreate, TrackInDB
from src.services.storage_service import storage_service

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.post("", response_model=TrackInDB, status_code=status.HTTP_201_CREATED)
async def create_track(
    track_in: TrackCreate = Depends(),
    audio_file: UploadFile = File(...),
    cover_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    audio_url = storage_service.upload_file(audio_file, storage_service.audio_bucket)
    cover_url = storage_service.upload_file(cover_file, storage_service.covers_bucket)

    new_track = Track(
        **track_in.model_dump(),
        audio_url=audio_url,
        cover_url=cover_url,
        artist_id=current_artist.user_id,
    )
    db.add(new_track)
    await db.commit()

    # Eagerly load the relationships required by the response model
    # to prevent lazy loading issues during serialization.
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
    new_track = result.scalar_one()
    return new_track


@router.put("/{track_id}", response_model=TrackInDB)
async def update_track(
    track_id: int,
    track_in: TrackCreate = Depends(),
    audio_file: UploadFile | None = Depends(empty_string_to_none),
    cover_file: UploadFile | None = Depends(empty_string_to_none),
    db: AsyncSession = Depends(get_db_session),
    current_artist: Artist = Depends(get_current_artist),
):
    result = await db.execute(
        select(Track)
        .options(
            selectinload(Track.artist)
            .selectinload(Artist.country)
            .selectinload(Country.continent),
            selectinload(Track.genres),
        )
        .filter(Track.track_id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if track.artist_id != current_artist.user_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this track"
        )

    for field, value in track_in.model_dump(exclude_unset=True).items():
        setattr(track, field, value)

    if audio_file:
        storage_service.delete_file(track.audio_url)
        track.audio_url = storage_service.upload_file(
            audio_file, storage_service.audio_bucket
        )
    if cover_file:
        storage_service.delete_file(track.cover_url)
        track.cover_url = storage_service.upload_file(
            cover_file, storage_service.covers_bucket
        )

    await db.commit()
    await db.refresh(track)
    return track


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

    storage_service.delete_file(track.audio_url)
    storage_service.delete_file(track.cover_url)

    await db.delete(track)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{track_id}/stream")
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
        .filter(Track.track_id == track_id)
    )
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Log stream event
    stream_event = StreamEvent(
        event_timestamp=datetime.now(timezone.utc),
        user_id=current_user.user_id,
        duration_milliseconds=0,  # Placeholder, could be updated on client side
        was_skipped=False,  # Placeholder
        track_id=track.track_id,
    )
    db.add(stream_event)
    await db.commit()

    bucket_name = storage_service.audio_bucket
    object_name = track.audio_url.split("/")[-1]

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


@router.post("/{seed_track_id}/recommendations", response_model=list[TrackInDB])
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
