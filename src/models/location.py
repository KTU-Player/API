import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Continent(Base):
    __tablename__ = "continent"

    continent_id: Mapped[int] = mapped_column(primary_key=True)
    continent_name: Mapped[str] = mapped_column(sa.String(255))


class Country(Base):
    __tablename__ = "country"

    country_id: Mapped[int] = mapped_column(primary_key=True)
    country_name: Mapped[str] = mapped_column(sa.String(255))
    iso_code_2: Mapped[str] = mapped_column(sa.String(2))
    iso_code_3: Mapped[str] = mapped_column(sa.String(3))
    calling_code: Mapped[str] = mapped_column(sa.String(255))
    currency_code: Mapped[str] = mapped_column(sa.String(255))
    continent_id: Mapped[int] = mapped_column(sa.ForeignKey("continent.continent_id"))

    continent: Mapped["Continent"] = relationship(back_populates="countries")


Continent.countries = relationship(
    "Country", order_by=Country.country_id, back_populates="continent"
)
