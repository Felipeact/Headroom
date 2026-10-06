"""Load sample data into the local database: `python -m app.fixtures.load harbor_street`.

Spec 18, AD-069. The sample goes through the real services: the owner and business
through `accounts`, each bank through `bank_sync`'s connect and sync with
`FixturePlaidClient` in place of Plaid. So the sign flip, labels, audit entries and
`transactions.synced` events are the ones a real bank gets. Exit codes: 0 loaded or
already loaded, 1 refused or failed, 2 usage.
"""

import argparse
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

import structlog
from pydantic import ValidationError
from sqlalchemy import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import subscriptions
from app.db import get_sessionmaker
from app.fixtures import harbor_street
from app.fixtures.harbor_street import SampleBusiness
from app.fixtures.plaid import ACCESS_TOKEN, FixturePlaidClient
from app.log import configure_logging
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import service as bank_service
from app.settings import get_settings

__all__ = ["ACCESS_TOKEN", "is_local_database", "load", "main"]

log = structlog.get_logger(__name__)

FIXTURES: dict[str, Callable[[int], SampleBusiness]] = {
    "harbor_street": harbor_street.generate
}
DEFAULT_CLERK_USER_ID = "user_sample_harbor_street"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
REFUSED_REMOTE = "Refusing to load sample data into a non-local database."
# 6:02 AM in Toronto on the reference day: the dashboard's "Updated today at 6:02 AM".
SYNCED_AT = datetime(2026, 9, 26, 10, 2, tzinfo=UTC)
PUBLIC_TOKEN = "sample-public-token"


class LoadRefusedError(Exception):
    """The owner already owns a business that is not this sample, fully loaded."""


def is_local_database(url: str) -> bool:
    return make_url(url).host in LOCAL_HOSTS


def _owned(
    session: Session, user_id: uuid.UUID
) -> accounts_service.MemberBusiness | None:
    owned = [
        b
        for b in accounts_service.list_businesses(session, user_id)
        if b.role == accounts_service.Role.OWNER
    ]
    return owned[0] if owned else None


def _is_loaded(
    session: Session, business: accounts_service.MemberBusiness, sample: SampleBusiness
) -> bool:
    banks = sorted(
        c.institution_name
        for c in bank_service.list_connections(session, business_id=business.id)
    )
    return business.name == sample.business.name and banks == sorted(
        b.institution_name for b in sample.banks
    )


def load(
    session: Session, sample: SampleBusiness, *, clerk_user_id: str
) -> tuple[uuid.UUID, bool]:
    """Load `sample` for the owner with this Clerk ID; returns (business ID, was loaded).

    Raises `LoadRefusedError` when the owner owns any other business, including a
    partial load of this sample.
    """
    user = accounts_service.get_or_create_user(session, clerk_user_id)
    existing = _owned(session, user.id)
    if existing is not None:
        if _is_loaded(session, existing, sample):
            return existing.id, False
        raise LoadRefusedError(
            f"This user already owns business {existing.id}, which is not a fully loaded"
            " sample. Use another --clerk-user-id or a fresh local database."
        )
    business = accounts_service.create_business(
        session,
        user_id=user.id,
        name=sample.business.name,
        province=sample.business.province,
        time_zone=sample.business.time_zone,
    )
    connected = []
    for bank in sample.banks:
        plaid = FixturePlaidClient(bank, sample.history, business_id=business.id)
        connection = bank_service.connect_bank(
            session,
            plaid,
            business_id=business.id,
            user_id=user.id,
            public_token=PUBLIC_TOKEN,
        )
        connected.append((plaid, connection))
    # A new connection counts only checking as cash (AD-040); savings is cash here too.
    for _, connection in connected:
        for account in connection.accounts:
            if account.type == "savings":
                bank_service.update_account(
                    session,
                    business_id=business.id,
                    account_id=account.id,
                    user_id=user.id,
                    included=True,
                    primary=False,
                )
    for plaid, connection in connected:
        bank_service.sync_connection(
            session,
            plaid,
            business_id=business.id,
            connection_id=connection.id,
            now=SYNCED_AT,
        )
    return business.id, True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.fixtures.load",
        description="Load synthetic sample data into the local database.",
    )
    parser.add_argument("fixture", choices=sorted(FIXTURES))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--clerk-user-id", default=DEFAULT_CLERK_USER_ID)
    args = parser.parse_args(argv)

    configure_logging()
    try:
        database_url = get_settings().database_url
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]) for e in exc.errors())
        print(f"Settings are missing or invalid: {fields}.", file=sys.stderr)
        return 1
    if not is_local_database(database_url):
        print(REFUSED_REMOTE, file=sys.stderr)
        return 1

    subscriptions.register()
    sample = FIXTURES[args.fixture](args.seed)
    try:
        with get_sessionmaker()() as session:
            business_id, created = load(
                session, sample, clerk_user_id=args.clerk_user_id
            )
    except LoadRefusedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except SQLAlchemyError as exc:
        print(f"The database failed: {type(exc).__name__}.", file=sys.stderr)
        return 1
    if not created:
        print(f"already loaded: {business_id}")
        return 0
    log.info(
        "fixture.loaded",
        fixture=args.fixture,
        seed=args.seed,
        business_id=str(business_id),
        transactions=len(sample.history),
    )
    print(business_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
