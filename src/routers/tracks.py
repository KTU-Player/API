from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
import json

from .. import schemas
from ..database import get_db_session
from ..services.track_service import track_service

router = APIRouter(tags=["Tracks & Genres"])


@router.get("/tracks", response_model=list[schemas.TrackInDB])
async def read_tracks(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve all tracks.
    """
    tracks = await track_service.get_all_tracks(db, skip=skip, limit=limit)
    return tracks


@router.post(
    "/tracks", response_model=schemas.TrackInDB, status_code=status.HTTP_201_CREATED
)
async def create_track(
    audio_file: Annotated[UploadFile, File()],
    cover_file: Annotated[UploadFile, File()],
    track_in_str: Annotated[str, Form()],
    artist_id: Annotated[int, Form()],
    genre_ids: Annotated[str, Form()],  # Expect a JSON string of a list
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new track with audio and cover art.
    """
    try:
        track_in = schemas.TrackCreate.model_validate_json(track_in_str)
        genre_ids_list = json.loads(genre_ids)
        if not isinstance(genre_ids_list, list):
            raise ValueError()
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format for genre_ids (must be a JSON array of integers) or track_in (must be a JSON object).",
        )

    return await track_service.create_track(
        db=db,
        track=track_in,
        artist_id=artist_id,
        genre_ids=genre_ids_list,
        audio_file=audio_file,
        cover_file=cover_file,
    )


@router.get("/tracks/{track_id}", response_model=schemas.TrackInDB)
async def read_track(track_id: int, db: AsyncSession = Depends(get_db_session)):
    """
    Get a specific track by its ID.
    """
    db_track = await track_service.get_track_by_id(db, track_id=track_id)
    if db_track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Track not found"
        )
    return db_track


@router.get("/genres", response_model=list[schemas.Genre])
async def read_genres(db: AsyncSession = Depends(get_db_session)):
    """
    Retrieve all genres.
    """
    genres = await track_service.get_genres(db)
    return genres
