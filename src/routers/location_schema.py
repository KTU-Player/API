from pydantic import BaseModel


class Country(BaseModel):
    country_id: int
    name: str

    class Config:
        from_attributes = True
