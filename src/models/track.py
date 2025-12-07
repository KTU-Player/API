from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import Artist


class Genre(Base):
    __tablename__ = "genre"

    genre_id: Mapped[int] = mapped_column(primary_key=True)
    genre_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    era_of_origin: Mapped[str | None] = mapped_column(sa.String(255))

    tracks: Mapped[list["Track"]] = relationship(
        secondary="track_genre", back_populates="genres"
    )


class Track(Base):
    __tablename__ = "track"

    track_id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    audio_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cover_key: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    release_date: Mapped[date] = mapped_column(sa.Date, nullable=False, default=date.today())
    is_explicit: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    artist_id: Mapped[int] = mapped_column(sa.ForeignKey("artist.user_id"))

    artist: Mapped["Artist"] = relationship(back_populates="tracks")
    genres: Mapped[list["Genre"]] = relationship(
        secondary="track_genre", back_populates="tracks"
    )


# A bit of a circular dependency dance
Artist.tracks = relationship("Track", order_by=Track.track_id, back_populates="artist")


class TrackGenre(Base):
    __tablename__ = "track_genre"

    track_id: Mapped[int] = mapped_column(
        sa.ForeignKey("track.track_id"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        sa.ForeignKey("genre.genre_id"), primary_key=True
    )
