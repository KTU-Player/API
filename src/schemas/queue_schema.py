from pydantic import BaseModel, ConfigDict
from .track_schema import Track


class QueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position_order: int
    track: Track


class Queue(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    queue_id: int
    user_id: int
    items: list[QueueItem] = []
