import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import FreeUser
from .track import Track


class Queue(Base):
    __tablename__ = "queue"

    queue_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("free_user.user_id"), unique=True
    )

    user: Mapped["FreeUser"] = relationship(back_populates="queue")
    items: Mapped[list["QueueItem"]] = relationship(back_populates="queue")


FreeUser.queue = relationship("Queue", uselist=False, back_populates="user")


class QueueItem(Base):
    __tablename__ = "queue_item"

    queue_id: Mapped[int] = mapped_column(
        sa.ForeignKey("queue.queue_id"), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(
        sa.ForeignKey("track.track_id"), primary_key=True
    )
    position_order: Mapped[int] = mapped_column(nullable=False)

    queue: Mapped["Queue"] = relationship(back_populates="items")
    track: Mapped["Track"] = relationship()
