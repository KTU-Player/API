from datetime import date
from pydantic import BaseModel, EmailStr, SecretStr, ConfigDict

from .location_schema import Country


# --- Base User Schemas ---
class BaseUserBase(BaseModel):
    email: EmailStr
    display_name: str
    date_of_birth: date


class BaseUserCreate(BaseUserBase):
    password: SecretStr


class BaseUserInDB(BaseUserBase):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    is_active: bool
    creation_date: date
    last_login_date: date | None
    date_of_birth: date


# --- Free User Schemas ---
class FreeUserBase(BaseModel):
    pass  # Fields are now in BaseUserBase


class FreeUserCreate(BaseUserCreate, FreeUserBase):
    pass


class FreeUserInDB(BaseUserInDB, FreeUserBase):
    model_config = ConfigDict(from_attributes=True)
    pass


# --- Premium User Schemas ---
class PremiumUserInDB(FreeUserInDB):
    model_config = ConfigDict(from_attributes=True)
    pass


# --- Artist Schemas ---
class ArtistBase(BaseModel):
    biography: str | None = None
    social_media_link: str | None = None


class ArtistCreate(BaseUserCreate, ArtistBase):
    country_id: int


class ArtistInDB(BaseUserInDB, ArtistBase):
    model_config = ConfigDict(from_attributes=True)
    country: Country


# --- General User Read Schema ---
class User(BaseUserInDB):
    model_config = ConfigDict(from_attributes=True)

    # These fields will be populated based on the user type
    biography: str | None = None
    social_media_link: str | None = None
    country: Country | None = None


class ArtistForTrack(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    display_name: str
