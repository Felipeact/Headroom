from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DATABASE_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local")

    database_url: str
    sentry_dsn: str | None = None
    sentry_environment: str = "local"
    # PEM public key of the Clerk instance; verifies session tokens with no network call.
    clerk_jwt_key: str
    # Origins allowed in a token's `azp` claim, comma-separated. Empty: `azp` is not checked.
    clerk_authorized_parties: Annotated[list[str], NoDecode] = []

    @field_validator("database_url")
    @classmethod
    def require_psycopg_scheme(cls, value: str) -> str:
        if not value.startswith(DATABASE_SCHEME):
            raise ValueError(f"DATABASE_URL must start with {DATABASE_SCHEME}")
        return value

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
