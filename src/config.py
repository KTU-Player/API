from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_ADMIN_USER: str = "postgres"
    DB_ADMIN_PASSWORD: str = "password"
    DB_NAME: str = "music_app_db"

    MINIO_API_PORT: int = 9000
    MINIO_HOST: str = "localhost"
    MINIO_ENDPOINT: str = f"{MINIO_HOST}:{MINIO_API_PORT}"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_AUDIO_BUCKET: str = "audio"
    MINIO_COVERS_BUCKET: str = "covers"

    JWT_SECRET_KEY: str = "your-secret-key"
    JWT_ALGORITHM: str = "HS256"

    @computed_field
    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.DB_ADMIN_USER,
            password=self.DB_ADMIN_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
        )


settings = Settings()
