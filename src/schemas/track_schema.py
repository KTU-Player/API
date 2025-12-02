from datetime import date
from pydantic import BaseModel, ConfigDict

from .user_schema import ArtistInDB


class Genre(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    genre_id: int
    genre_name: str
    description: str | None
    era_of_origin: str | None


class TrackBase(BaseModel):
    title: str
    duration_miliseconds: int
    is_explicit: bool
    release_date: date


class TrackCreate(TrackBase):
    # URLs will be set by the system after upload, not provided by the user
    pass


class TrackInDB(TrackBase):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    audio_url: str
    cover_url: str
    artist: ArtistInDB
    genres: list[Genre] = []
