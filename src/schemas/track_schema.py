from datetime import date
from pydantic import BaseModel, ConfigDict, field_validator

from src.services.storage_service import storage_service
from .user_schema import ArtistForTrack


class GenreForTrack(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    genre_id: int
    genre_name: str


class TrackBase(BaseModel):
    title: str
    is_explicit: bool


class TrackCreate(TrackBase):
    genre_ids: list[int] = []
    pass


class TrackUpdate(TrackBase):
    title: str | None = None
    is_explicit: bool | None = None
    genre_ids: list[int] | None = []


class Track(TrackBase):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    release_date: date
    artist: ArtistForTrack
    genres: list[GenreForTrack] = []
    audio_key: str | None
    cover_key: str | None

    # @field_validator("audio_url", mode="before")
    # def populate_audio_url(cls, v, values):
    #     if "audio_key" in values.data:
    #         return storage_service.get_presigned_url(
    #             values.data["audio_key"], storage_service.audio_bucket
    #         )
    #     return v

    # @field_validator("cover_url", mode="before")
    # def populate_cover_url(cls, v, values):
    #     if "cover_key" in values.data:
    #         return storage_service.get_presigned_url(
    #             values.data["cover_key"], storage_service.covers_bucket
    #         )
    #     return v
