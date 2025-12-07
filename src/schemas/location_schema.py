from pydantic import BaseModel, ConfigDict


class Continent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    continent_id: int
    continent_name: str


class Country(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    country_id: int
    country_name: str
    iso_code_2: str
    iso_code_3: str
    calling_code: str
    currency_code: str
    continent: Continent
