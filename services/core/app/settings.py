from functools import lru_cache
from typing import Annotated, Literal

from cryptography.fernet import Fernet
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DATABASE_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    # hide_input_in_errors: a validation error reaches deploy logs (the pre-deploy
    # migration's traceback), so it must name the field, never the value (spec 12).
    model_config = SettingsConfigDict(env_file=".env.local", hide_input_in_errors=True)

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
    # Public URL of POST /v1/webhooks/plaid, sent on every link token. Unset (local runs):
    # Plaid sends no webhooks, and banks sync on connect and from the nightly job.
    plaid_webhook_url: str | None = None
    # Fernet keys for Plaid access tokens, comma-separated; the first encrypts, any decrypts.
    token_encryption_keys: Annotated[list[str], NoDecode]
    # The forecasting method (spec 21, AD-078); `rolling_average` is also the fallback.
    forecast_strategy: Literal["recurring_pattern", "rolling_average"] = (
        "recurring_pattern"
    )

    # Email (spec 28). No default for the sender, for the same reason as `plaid_env`: a
    # deploy that forgot it must not quietly print emails instead of sending them.
    email_sender: Literal["console", "resend"]
    resend_api_key: str | None = None
    # `Headroom <alerts@...>`, on a domain verified in Resend.
    email_from: str
    # Headroom's postal address, required in every email's footer by CASL.
    email_mailing_address: str
    # Public base URLs: the web app (footer links) and this API (List-Unsubscribe).
    web_url: str
    api_public_url: str
    # Clerk Backend API key: the API reads a recipient's address from Clerk at send time.
    clerk_secret_key: str
    # The weekly metrics report (spec 32). All optional: with no recipients the job sends
    # nothing, and with no PostHog settings the two figures that come from PostHog read
    # "unavailable". `posthog_app_host` is the region's app host (`https://us.posthog.com`),
    # not the ingestion host the web app sends events to.
    posthog_app_host: str | None = None
    posthog_project_id: str | None = None
    posthog_personal_api_key: str | None = None
    metrics_report_recipients: Annotated[list[str], NoDecode] = []

    @model_validator(mode="after")
    def require_resend_key(self) -> "Settings":
        if self.email_sender == "resend" and not self.resend_api_key:
            raise ValueError("resend_api_key is required when email_sender is resend")
        return self

    @field_validator("resend_api_key", mode="before")
    @classmethod
    def empty_resend_key_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def require_psycopg_scheme(cls, value: str) -> str:
        if not value.startswith(DATABASE_SCHEME):
            raise ValueError(f"DATABASE_URL must start with {DATABASE_SCHEME}")
        return value

    @field_validator("plaid_webhook_url", mode="before")
    @classmethod
    def empty_webhook_url_is_unset(cls, value: object) -> object:
        # `PLAID_WEBHOOK_URL=` copied from .env.example means "no webhook", not "".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "posthog_app_host",
        "posthog_project_id",
        "posthog_personal_api_key",
        mode="before",
    )
    @classmethod
    def empty_posthog_setting_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("metrics_report_recipients", mode="before")
    @classmethod
    def split_recipients(cls, value: object) -> object:
        if isinstance(value, str):
            return [address.strip() for address in value.split(",") if address.strip()]
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
                raise ValueError(
                    "TOKEN_ENCRYPTION_KEYS holds a value that is not a Fernet key"
                ) from None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


class DocsSettings(BaseSettings):
    """Only the docs switch (spec 33, door 6).

    The routes are chosen when `app.main` is imported, which must work without the other
    settings (AD-001), so this reads nothing else.
    """

    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    api_docs_enabled: bool = False


def docs_enabled() -> bool:
    return DocsSettings().api_docs_enabled
