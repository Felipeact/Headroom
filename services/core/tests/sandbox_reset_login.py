"""Force a business's banks into Plaid's "login required" state, in the sandbox only.

Spec 17's end-to-end test runs `uv run python -m tests.sandbox_reset_login <business>`, where
`<business>` is the business's ID or its exact name (the browser test knows only the name).
For each connection of the business it calls `/sandbox/item/reset_login`, then syncs the
connection, so the API records the login problem the way it would in real use. It is
never a route: the access token stays in the backend, and it refuses to run unless
`PLAID_ENV` is `sandbox`.
"""

import sys
import uuid

from plaid import ApiClient, Configuration, Environment
from plaid.api.plaid_api import PlaidApi
from plaid.model.sandbox_item_reset_login_request import SandboxItemResetLoginRequest
from sqlalchemy import select

from app.db import get_sessionmaker
from app.modules.accounts.models import Business
from app.modules.bank_sync import service
from app.modules.bank_sync.models import BankConnection
from app.modules.bank_sync.plaid import PlaidError, get_plaid_client
from app.modules.bank_sync.tokens import decrypt_access_token
from app.settings import get_settings


def sandbox_api() -> PlaidApi:
    settings = get_settings()
    if settings.plaid_env != "sandbox":
        raise SystemExit("refusing to run: PLAID_ENV is not sandbox")
    configuration = Configuration(
        host=Environment.Sandbox,
        api_key={"clientId": settings.plaid_client_id, "secret": settings.plaid_secret},
    )
    return PlaidApi(ApiClient(configuration))


def reset_login(business_id: uuid.UUID) -> int:
    """Reset every connection of the business and sync it; returns how many."""
    api = sandbox_api()
    with get_sessionmaker()() as session:
        connections = list(
            session.scalars(
                select(BankConnection).where(BankConnection.business_id == business_id)
            )
        )
        session.expunge_all()
    for connection in connections:
        api.sandbox_item_reset_login(
            SandboxItemResetLoginRequest(
                access_token=decrypt_access_token(connection.access_token_ciphertext)
            )
        )
        with get_sessionmaker()() as session:
            try:
                service.sync_connection(
                    session,
                    get_plaid_client(),
                    business_id=business_id,
                    connection_id=connection.id,
                )
            except PlaidError as exc:
                if exc.error_code != service.LOGIN_REQUIRED:
                    raise
    return len(connections)


def business_id(business: str) -> uuid.UUID:
    """The ID itself, or the ID of the one business with exactly this name."""
    try:
        return uuid.UUID(business)
    except ValueError:
        pass
    with get_sessionmaker()() as session:
        ids = list(
            session.scalars(select(Business.id).where(Business.name == business))
        )
    if len(ids) != 1:
        raise SystemExit(f"expected one business named {business!r}, found {len(ids)}")
    return ids[0]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python -m tests.sandbox_reset_login <business id or name>"
        )
    count = reset_login(business_id(sys.argv[1]))
    print(f"reset {count} connection(s)")
