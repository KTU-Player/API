from pydantic import BaseModel, ConfigDict
from .location_schema import Country


class AddressBase(BaseModel):
    postal_code: str
    province: str | None = None
    city: str
    street: str


class AddressCreate(AddressBase):
    user_id: int
    country_id: int


class Address(AddressBase):
    model_config = ConfigDict(from_attributes=True)
    address_id: int
    country: Country
