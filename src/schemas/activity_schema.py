from datetime import datetime
from pydantic import BaseModel, ConfigDict

from .track_schema import TrackInDB


class UserActivityEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: int
    timestamp: datetime
    user_id: int


class SearchEvent(UserActivityEvent):
    model_config = ConfigDict(from_attributes=True)

    query: str


class StreamEvent(UserActivityEvent):
    model_config = ConfigDict(from_attributes=True)

    duration_miliseconds: int
    was_skipped: bool
    track: TrackInDB
