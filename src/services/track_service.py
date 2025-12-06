from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import UploadFile
import uuid
import io

from .. import models, schemas
from .storage_service import storage_service


class TrackService:
    async def get_track_by_id(
        self, db: AsyncSession, track_id: int
    ) -> models.Track | None:
        stmt = (
            select(models.Track)
            .where(models.Track.track_id == track_id)
            .options(
                selectinload(models.Track.artist), selectinload(models.Track.genres)
            )
        )
        track = await db.scalar(stmt)
        if track:
            track.audio_url = storage_service.get_presigned_url(track.audio_url)
            track.cover_url = storage_service.get_presigned_url(track.cover_url)
        return track

    async def get_all_tracks(
        self, db: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[models.Track]:
        stmt = (
            select(models.Track)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(models.Track.artist), selectinload(models.Track.genres)
            )
        )
        result = await db.execute(stmt)
        tracks = result.scalars().all()
        for track in tracks:
            track.audio_url = storage_service.get_presigned_url(track.audio_url)
            track.cover_url = storage_service.get_presigned_url(track.cover_url)
        return list(tracks)

    async def create_track(
        self,
        db: AsyncSession,
        track: schemas.TrackCreate,
        artist_id: int,
        genre_ids: list[int],
        audio_file: UploadFile,
        cover_file: UploadFile,
    ) -> models.Track:
        if audio_file.filename is None or cover_file.filename is None:
            raise ValueError("Audio and cover files are required.")

        audio_obj_name = f"audio/{uuid.uuid4()}_{audio_file.filename.replace(" ", "_").lower()}"
        cover_obj_name = f"covers/{uuid.uuid4()}_{cover_file.filename.replace(" ", "_").lower()}"

        audio_data = await audio_file.read()
        cover_data = await cover_file.read()

        if audio_file.content_type is not None and cover_file.content_type is not None:
            storage_service.upload_file(
                audio_obj_name,
                io.BytesIO(audio_data),
                len(audio_data),
                audio_file.content_type,
            )
            storage_service.upload_file(
                cover_obj_name,
                io.BytesIO(cover_data),
                len(cover_data),
                cover_file.content_type,
            )

        db_track = models.Track(
            **track.model_dump(),
            artist_id=artist_id,
            audio_url=audio_obj_name,
            cover_url=cover_obj_name,
        )

        if genre_ids:
            genres = await db.execute(
                select(models.Genre).where(models.Genre.genre_id.in_(genre_ids))
            )
            db_track.genres.extend(genres.scalars().all())

        db.add(db_track)
        await db.commit()
        await db.refresh(db_track)
        return db_track

    async def get_genres(self, db: AsyncSession) -> list[models.Genre]:
        stmt = select(models.Genre)
        result = await db.execute(stmt)
        return list(result.scalars().all())


track_service = TrackService()
