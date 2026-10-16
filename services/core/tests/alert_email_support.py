"""The sample alert email (spec 29): Harbor Street seed 0 with the mockup's $5,000 minimum.

`send_sample()` loads the sample, registers its owner in a fake Clerk as Dana, and sets the
minimum through the API with every subscription registered, so the email goes out the way
it would in production: request -> forecast_inputs.changed -> alert.created -> email.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import subscriptions
from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import clerk
from app.modules.accounts import repository as accounts_repository
from app.modules.accounts import service as accounts_service
from app.modules.alerts.models import Alert
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.api import get_now
from app.modules.notifications import senders
from app.modules.notifications.models import EmailDelivery
from app.modules.notifications.senders import OutgoingEmail
from tests.email_support import FakeClerkUsers, FakeEmailSender
from tests.test_forecast_recompute import NOW
from tests.test_recurring_sample import load_sample

client = TestClient(app)

DANA = "dana@example.test"
WEB = "https://app.example.test"


@dataclass
class SampleEmail:
    business_id: uuid.UUID
    owner_id: uuid.UUID
    owner_clerk_id: str
    alert_id: uuid.UUID
    sent: list[OutgoingEmail]
    deliveries: list[EmailDelivery]
    params: dict[str, Any]


def send_sample() -> SampleEmail:
    sample = load_sample(0)
    business_id = uuid.UUID(sample.business_id)
    with get_sessionmaker()() as session:
        (owner_id,) = accounts_service.owner_ids(session, business_id=business_id)
        owner_clerk_id = accounts_repository.clerk_user_id(session, owner_id)
    assert owner_clerk_id is not None
    sender = FakeEmailSender()
    users = FakeClerkUsers()
    users.set(owner_clerk_id, DANA, "Dana")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(senders, "get_email_sender", lambda: sender)
        mp.setattr(clerk, "get_clerk_users", lambda: users)
        mp.setattr(forecasting_service, "clock", lambda: NOW)
        app.dependency_overrides[get_now] = lambda: NOW
        try:
            subscriptions.register()
            response = client.put(
                f"/v1/businesses/{business_id}/minimum-balance",
                json={"amount_cents": 500000},
                headers=sample.headers,
            )
        finally:
            app.dependency_overrides.pop(get_now, None)
    assert response.status_code == 200, response.text
    with get_sessionmaker()() as session:
        (alert,) = session.scalars(
            select(Alert).where(Alert.business_id == business_id)
        )
        deliveries = list(
            session.scalars(
                select(EmailDelivery).where(EmailDelivery.business_id == business_id)
            )
        )
        session.expunge_all()
    assert len(deliveries) == 1
    return SampleEmail(
        business_id=business_id,
        owner_id=owner_id,
        owner_clerk_id=owner_clerk_id,
        alert_id=alert.id,
        sent=sender.sent,
        deliveries=deliveries,
        params=json.loads(json.dumps(deliveries[0].params)),
    )
