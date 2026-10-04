from functools import lru_cache
from typing import Annotated, Literal

from cryptography.fernet import Fernet
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
    # Plaid (spec 12). No default for the environment: a production deploy that forgot it
    # must not quietly talk to the sandbox.
    plaid_client_id: str
    plaid_secret: str
    plaid_env: Literal["sandbox", "production"]
    # Fernet keys for Plaid access tokens, comma-separated; the first encrypts, any decrypts.
    token_encryption_keys: Annotated[list[str], NoDecode]

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

    @field_validator("token_encryption_keys", mode="before")
    @classmethod
    def split_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [key.strip() for key in value.split(",") if key.strip()]
        return value

    @field_validator("token_encryption_keys")
    @classmethod
    def require_fernet_keys(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("TOKEN_ENCRYPTION_KEYS needs at least one Fernet key")
        for key in value:
            try:
                Fernet(key)
            except ValueError:
                # No key text in the message: it would end up in logs.
                raise ValueError(
                    "TOKEN_ENCRYPTION_KEYS holds a value that is not a Fernet key"
                ) from None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
