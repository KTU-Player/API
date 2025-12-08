from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import UploadFile, HTTPException, status

from .. import models, schemas
from .storage_service import storage_service


class TrackService:
    async def get_track_by_id(
        self, db: AsyncSession, track_id: int
    ) -> models.Track | None:
        stmt = (
            select(models.Track)
            .where(models.Track.track_id == track_id, models.Track.is_active.is_(True))
            .options(
                selectinload(models.Track.artist), selectinload(models.Track.genres)
            )
        )
        return await db.scalar(stmt)

    async def get_all_tracks(
        self,
        db: AsyncSession,
        current_user: models.BaseUser | None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[models.Track]:
        stmt = (
            select(models.Track)
            .where(models.Track.is_active.is_(True))
            .options(
                selectinload(models.Track.artist), selectinload(models.Track.genres)
            )
        )

        if current_user and current_user.date_of_birth:
            today = date.today()
            age = (
                today.year
                - current_user.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (
                        current_user.date_of_birth.month,
                        current_user.date_of_birth.day,
                    )
                )
            )
            if age < 18:
                stmt = stmt.where(models.Track.is_explicit.is_(False))

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_tracks_by_artist(
        self, db: AsyncSession, artist_id: int, skip: int = 0, limit: int = 100
    ) -> list[models.Track]:
        stmt = (
            select(models.Track)
            .where(models.Track.artist_id == artist_id, models.Track.is_active.is_(True))
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(models.Track.artist), selectinload(models.Track.genres)
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

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

        audio_key = storage_service.upload_file(
            audio_file, storage_service.audio_bucket
        )
        cover_key = storage_service.upload_file(
            cover_file, storage_service.covers_bucket
        )

        db_track = models.Track(
            title=track.title,
            is_explicit=track.is_explicit,
            artist_id=artist_id,
            audio_key=audio_key,
            cover_key=cover_key,
        )

        if genre_ids:
            genres = await db.execute(
                select(models.Genre).where(models.Genre.genre_id.in_(genre_ids))
            )
            db_track.genres.extend(genres.scalars().all())

        db.add(db_track)
        await db.commit()
        return db_track

    async def update_track(
        self,
        db: AsyncSession,
        track_id: int,
        track_in: schemas.TrackUpdate,
        current_artist_id: int,
        cover_file: UploadFile | None,
        genre_ids: list[int] | None = None,
    ) -> models.Track | None:
        result = await db.execute(
            select(models.Track)
            .options(selectinload(models.Track.genres))
            .filter(models.Track.track_id == track_id, models.Track.is_active.is_(True))
        )
        track = result.scalar_one_or_none()

        if not track:
            return None
        if track.artist_id != current_artist_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this track",
            )

        for field, value in track_in.model_dump(exclude_unset=True).items():
            setattr(track, field, value)

        if genre_ids is not None:
            genres = await db.execute(
                select(models.Genre).where(models.Genre.genre_id.in_(genre_ids))
            )
            track.genres.clear()
            track.genres.extend(genres.scalars().all())

        if cover_file:
            if not cover_file.content_type or not cover_file.content_type.startswith(
                "image/"
            ):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Invalid cover file type. Only image files are allowed.",
                )

            storage_service.delete_file(track.cover_key, storage_service.covers_bucket)
            track.cover_key = storage_service.upload_file(
                cover_file, storage_service.covers_bucket
            )

        await db.commit()
        return track

    async def get_genres(self, db: AsyncSession) -> list[models.Genre]:
        stmt = select(models.Genre)
        result = await db.execute(stmt)
        return list(result.scalars().all())


track_service = TrackService()
