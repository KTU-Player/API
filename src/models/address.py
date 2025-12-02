import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import FreeUser
from .location import Country


class Address(Base):
    __tablename__ = "address"

    address_id: Mapped[int] = mapped_column(primary_key=True)
    postal_code: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    province: Mapped[str | None] = mapped_column(sa.String(255))
    city: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    street: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("free_user.user_id"), unique=True
    )
    country_id: Mapped[int] = mapped_column(sa.ForeignKey("country.country_id"))

    user: Mapped["FreeUser"] = relationship(back_populates="billing_address")
    country: Mapped["Country"] = relationship()


FreeUser.billing_address = relationship("Address", uselist=False, back_populates="user")
