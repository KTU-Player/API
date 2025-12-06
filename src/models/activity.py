from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from .base import Base
from .user import FreeUser
from .track import Track


class UserActivityEvent(Base):
    __tablename__ = "user_activity_event"

    event_id: Mapped[int] = mapped_column(primary_key=True)
    event_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("free_user.user_id"))

    user: Mapped["FreeUser"] = relationship(back_populates="activity_events")
    event_type: Mapped[str] = mapped_column(sa.String(50))

    __mapper_args__ = {
        "polymorphic_identity": "user_activity_event",
        "polymorphic_on": "event_type",
    }


FreeUser.activity_events = relationship(
    "UserActivityEvent", order_by=UserActivityEvent.event_id, back_populates="user"
)


class SearchEvent(UserActivityEvent):
    __tablename__ = "search_event"

    event_id: Mapped[int] = mapped_column(
        sa.ForeignKey("user_activity_event.event_id"), primary_key=True
    )
    query: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "search_event",
    }


class StreamEvent(UserActivityEvent):
    __tablename__ = "stream_event"

    event_id: Mapped[int] = mapped_column(
        sa.ForeignKey("user_activity_event.event_id"), primary_key=True
    )
    duration_milliseconds: Mapped[int] = mapped_column(nullable=False)
    was_skipped: Mapped[bool] = mapped_column(nullable=False)
    track_id: Mapped[int] = mapped_column(sa.ForeignKey("track.track_id"))

    track: Mapped["Track"] = relationship(back_populates="stream_events")

    __mapper_args__ = {
        "polymorphic_identity": "stream_event",
    }


Track.stream_events = relationship(
    "StreamEvent", order_by=StreamEvent.event_id, back_populates="track"
)
