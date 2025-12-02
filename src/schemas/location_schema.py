from pydantic import BaseModel


class Continent(BaseModel):
    continent_id: int
    continent_name: str

    class Config:
        from_attributes = True


class Country(BaseModel):
    country_id: int
    country_name: str
    iso_code_2: str
    iso_code_3: str
    calling_code: str
    currency_code: str
    continent: Continent

    class Config:
        from_attributes = True
