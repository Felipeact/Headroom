from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DATABASE_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local")

    database_url: str
    sentry_dsn: str | None = None
    sentry_environment: str = "local"

    @field_validator("database_url")
    @classmethod
    def require_psycopg_scheme(cls, value: str) -> str:
        if not value.startswith(DATABASE_SCHEME):
            raise ValueError(f"DATABASE_URL must start with {DATABASE_SCHEME}")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
