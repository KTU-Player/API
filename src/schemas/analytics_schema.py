from pydantic import BaseModel, ConfigDict


class ArtistAnalytics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    monthly_listeners: int
    total_streams: int
    top_track: str | None
    avg_duration_per_track: list[dict]
