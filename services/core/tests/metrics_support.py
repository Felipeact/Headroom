"""Fakes and planting helpers for the spec 32 tests. No test calls PostHog."""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete

from app.analytics import PostHogError
from app.db import get_sessionmaker
from app.modules.accounts.models import Business, Invitation, Membership, User
from app.modules.bank_sync.models import BankConnection
from app.modules.forecasting.models import (
    ForecastAccuracy,
    ForecastSnapshot,
)

# Monday 2026-10-19 is the report week; the report goes out on Tuesday the 27th.
WEEK = date(2026, 10, 19)
NOW = datetime(2026, 10, 27, 12, 5, tzinfo=UTC)
SIGNUP = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


class FakePostHogQuery:
    """Returns the numbers the test sets, records every query, or raises `error`."""

    def __init__(
        self,
        *,
        weekly_active: int = 0,
        alerts_opened: int = 0,
        error: PostHogError | None = None,
    ) -> None:
        self.weekly_active = weekly_active
        self.alerts_opened = alerts_opened
        self.error = error
        self.queries: list[str] = []

    def count(self, hogql: str) -> int:
        self.queries.append(hogql)
        if self.error is not None:
            raise self.error
        return self.weekly_active if "dashboard_viewed" in hogql else self.alerts_opened


def clear() -> None:
    """Empty every table the report reads, so a test starts from nothing."""
    with get_sessionmaker()() as session:
        for model in (
            ForecastAccuracy,
            ForecastSnapshot,
            BankConnection,
            Invitation,
            Membership,
            Business,
            User,
        ):
            session.execute(delete(model))
        session.commit()


def user(created_at: datetime) -> uuid.UUID:
    with get_sessionmaker()() as session:
        row = User(clerk_user_id=f"user_{uuid.uuid4().hex}", created_at=created_at)
        session.add(row)
        session.commit()
        return row.id


def business(name: str = "Harbor Street Plumbing") -> uuid.UUID:
    with get_sessionmaker()() as session:
        row = Business(name=name, province="ON", time_zone="America/Toronto")
        session.add(row)
        session.commit()
        return row.id


def member(business_id: uuid.UUID, user_id: uuid.UUID, role: str) -> None:
    with get_sessionmaker()() as session:
        session.add(Membership(business_id=business_id, user_id=user_id, role=role))
        session.commit()


def owner_with_business(
    signed_up: datetime, name: str = "Harbor Street Plumbing"
) -> tuple[uuid.UUID, uuid.UUID]:
    """A new owner and their business: (user id, business id)."""
    user_id = user(signed_up)
    business_id = business(name)
    member(business_id, user_id, "owner")
    return user_id, business_id


def connection(business_id: uuid.UUID, created_at: datetime) -> None:
    with get_sessionmaker()() as session:
        session.add(
            BankConnection(
                business_id=business_id,
                provider_item_id=f"item-{uuid.uuid4().hex}",
                provider_institution_id=f"ins-{uuid.uuid4().hex}",
                institution_name="Bank",
                access_token_ciphertext="x",
                created_at=created_at,
            )
        )
        session.commit()


def accuracy(
    business_id: uuid.UUID,
    *,
    target_week: date,
    horizon: int,
    forecast: int,
    actual: int,
) -> None:
    """One stored forecast error, pinned `horizon - 1` weeks before its target week."""
    with get_sessionmaker()() as session:
        snapshot = ForecastSnapshot(
            id=uuid.uuid4(),
            business_id=business_id,
            inputs_sha256=uuid.uuid4().hex * 2,
            strategy="recurring_pattern",
            as_of=target_week - timedelta(weeks=horizon),
            currency="CAD",
            opening_balance_cents=0,
            last_computed_at=datetime(2026, 9, 26, 10, tzinfo=UTC),
        )
        session.add(snapshot)
        session.flush()
        session.add(
            ForecastAccuracy(
                business_id=business_id,
                week_start=target_week - timedelta(weeks=horizon - 1),
                horizon=horizon,
                target_week_start=target_week,
                snapshot_id=snapshot.id,
                currency="CAD",
                forecast_cents=forecast,
                actual_cents=actual,
                error_cents=forecast - actual,
            )
        )
        session.commit()
