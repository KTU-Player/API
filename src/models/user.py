from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from .base import Base
from .location import Country


class BaseUser(Base):
    __tablename__ = "base_user"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    creation_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    last_login_date: Mapped[date | None] = mapped_column(TIMESTAMP(timezone=True))
    date_of_birth: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    __mapper_args__ = {
        "polymorphic_identity": "base_user",
    }


class FreeUser(BaseUser):
    __tablename__ = "free_user"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("base_user.user_id"), primary_key=True
    )

    __mapper_args__ = {
        "polymorphic_identity": "free_user",
        "polymorphic_load": "inline",
    }


class PremiumUser(FreeUser):
    __tablename__ = "premium_user"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("free_user.user_id"), primary_key=True
    )

    __mapper_args__ = {
        "polymorphic_identity": "premium_user",
        "polymorphic_load": "inline",
    }


class Artist(BaseUser):
    __tablename__ = "artist"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("base_user.user_id"), primary_key=True
    )
    biography: Mapped[str | None] = mapped_column(sa.String(255))
    social_media_link: Mapped[str | None] = mapped_column(sa.String(255))
    country_id: Mapped[int] = mapped_column(sa.ForeignKey("country.country_id"))

    country: Mapped["Country"] = relationship()

    __mapper_args__ = {
        "polymorphic_identity": "artist",
        "polymorphic_load": "inline",
    }
