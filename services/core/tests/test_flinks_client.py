"""Spec 17a: the Flinks HTTP client, over `httpx.MockTransport` (nothing calls Flinks)."""

import json
from collections.abc import Callable
from datetime import date

import httpx
import pytest

from app.modules.bank_sync.flinks import (
    PENDING,
    TIMEOUT_SECONDS,
    FlinksError,
    HttpxFlinksClient,
    account_type,
)

LOGIN_ID = "8b35f6c8-e7b6-41d3-98f8-08d68b7f8d31"
CUSTOMER = "customer-1"
BASE = f"/v3/{CUSTOMER}/BankingServices"

Handler = Callable[[httpx.Request], httpx.Response]

DETAIL = {
    "HttpStatusCode": 200,
    "Institution": "RBC Royal Bank",
    "InstitutionId": 14,
    "Login": {"Id": LOGIN_ID, "LastRefresh": "2026-10-15T07:30:00"},
    "Accounts": [
        {
            "Id": "acc-1",
            "Title": "Business Chequing",
            "AccountNumber": "00012345678901",
            "LastFourDigits": "8901",
            "Type": "Chequing",
            "Category": "Operations",
            "Currency": "CAD",
            "Balance": {"Current": 1500.5, "Available": 1400.5, "Limit": None},
            "Holder": {"Name": "Dana Holder"},
            "Transactions": [
                {
                    "Id": "tx-1",
                    "Date": "2026/10/01",
                    "Description": "RENT",
                    "Debit": 1200.0,
                    "Credit": None,
                    "Balance": 1500.5,
                }
            ],
        }
    ],
}


class Recorder:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []
        self.timeouts: list[object] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.timeouts.append(request.extensions.get("timeout"))
        return self.handler(request)

    def paths(self) -> list[str]:
        return [r.url.path.removeprefix(BASE + "/") for r in self.requests]

    def body(self, path: str) -> dict[str, object]:
        request = next(r for r in self.requests if r.url.path.endswith("/" + path))
        return dict(json.loads(request.content))


def flinks_api(
    *,
    detail_statuses: tuple[int, ...] = (200,),
    fail: dict[str, httpx.Response] | None = None,
) -> Handler:
    """Answers like Flinks. GetAccountsDetail then each async poll take the next status."""
    statuses = list(detail_statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix(BASE + "/")
        name = path.split("/")[0]
        if fail and name in fail:
            return fail[name]
        if name == "GenerateAuthorizeToken":
            return httpx.Response(200, json={"HttpStatusCode": 200, "Token": "token-1"})
        if name == "Authorize":
            return httpx.Response(
                200, json={"HttpStatusCode": 200, "RequestId": "req-1"}
            )
        if name in ("GetAccountsDetail", "GetAccountsDetailAsync"):
            code = statuses.pop(0) if statuses else 200
            if code == 202:
                return httpx.Response(
                    202, json={"HttpStatusCode": 202, "FlinksCode": PENDING}
                )
            return httpx.Response(200, json=DETAIL)
        if name in ("SetScheduledRefresh", "DeleteCard"):
            return httpx.Response(200, json={"StatusCode": 200})
        return httpx.Response(404)

    return handler


def mock_client(
    handler: Handler, *, instance: str = "toolbox"
) -> tuple[HttpxFlinksClient, Recorder, list[float]]:
    recorder = Recorder(handler)
    sleeps: list[float] = []
    client = HttpxFlinksClient(
        instance=instance,
        customer_id=CUSTOMER,
        auth_key="auth-key-secret",
        api_key="api-key-secret",
        redirect_url="http://localhost:3000/onboarding/bank",
        http=httpx.Client(transport=httpx.MockTransport(recorder)),
        sleep=sleeps.append,
    )
    return client, recorder, sleeps


@pytest.mark.parametrize(
    ("flinks_type", "ours"),
    [
        ("Chequing", "checking"),
        ("Savings", "savings"),
        ("CreditCard", "credit_card"),
        ("LineOfCredit", "line_of_credit"),
        ("Investment", "other"),
    ],
)
def test_account_type_mapping(flinks_type: str, ours: str) -> None:
    """C12."""
    assert account_type(flinks_type) == ours


def test_enable_nightly_refresh_body() -> None:
    """C14."""
    client, recorder, _ = mock_client(flinks_api())

    client.enable_nightly_refresh(LOGIN_ID)

    request = recorder.requests[-1]
    assert request.method == "PATCH"
    assert request.url.path == f"{BASE}/SetScheduledRefresh"
    assert recorder.body("SetScheduledRefresh") == {
        "loginId": LOGIN_ID,
        "isActivated": True,
    }
    assert request.headers["flinks-auth-key"] == "token-1"


def test_async_poll_budget_succeeds_within_budget() -> None:
    """C18: two pending polls, then data, inside a budget of 3."""
    client, recorder, sleeps = mock_client(flinks_api(detail_statuses=(202, 202, 202)))

    snapshot = client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)

    assert sleeps == [10, 10, 10]
    assert recorder.paths()[-3:] == ["GetAccountsDetailAsync/req-1"] * 3
    assert snapshot.accounts[0].account_id == "acc-1"


@pytest.mark.parametrize("polls", [3, 30])
def test_async_poll_budget_exhausted(polls: int) -> None:
    """C18: still 202 after the whole budget is OPERATION_PENDING."""
    client, recorder, sleeps = mock_client(
        flinks_api(detail_statuses=(202,) * (polls + 1))
    )

    with pytest.raises(FlinksError) as raised:
        client.accounts(LOGIN_ID, with_transactions=False, days="Days90", polls=polls)

    assert (raised.value.http_status, raised.value.flinks_code) == (202, PENDING)
    assert sleeps == [10] * polls
    assert recorder.paths().count("GetAccountsDetailAsync/req-1") == polls


def test_errors_carry_only_code() -> None:
    """C19: a 4xx keeps only the status and FlinksCode, never the body."""
    body = {
        "HttpStatusCode": 401,
        "FlinksCode": "INVALID_LOGIN",
        "Message": f"login {LOGIN_ID} is invalid",
    }
    client, _, _ = mock_client(
        flinks_api(fail={"Authorize": httpx.Response(401, json=body)})
    )

    with pytest.raises(FlinksError) as raised:
        client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)

    error = raised.value
    assert (error.http_status, error.flinks_code) == (401, "INVALID_LOGIN")
    assert LOGIN_ID not in str(error)
    # No chained exception carries the response body.
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__


def test_errors_carry_only_code_on_timeout() -> None:
    """C19: a timeout becomes a FlinksError with no status."""

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, _, _ = mock_client(timeout)

    with pytest.raises(FlinksError) as raised:
        client.connect_url()

    assert (raised.value.http_status, raised.value.flinks_code) == (None, "ReadTimeout")


def test_timeout_is_15s() -> None:
    """C19."""
    client, recorder, _ = mock_client(flinks_api())

    client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)

    assert TIMEOUT_SECONDS == 15
    for timeout in recorder.timeouts:
        assert timeout == {"connect": 15, "read": 15, "write": 15, "pool": 15}


def test_accounts_detail_body_excludes_identity() -> None:
    """C21."""
    client, recorder, _ = mock_client(flinks_api())

    snapshot = client.accounts(
        LOGIN_ID, with_transactions=True, days="Days365", polls=3
    )

    assert recorder.body("GetAccountsDetail") == {
        "RequestId": "req-1",
        "WithAccountIdentity": False,
        "WithKYC": False,
        "WithTransactions": True,
        "DaysOfTransactions": "Days365",
    }
    account = snapshot.accounts[0]
    assert account.mask == "8901"
    assert "00012345678901" not in repr(snapshot)
    assert "Dana Holder" not in repr(snapshot)
    tx = snapshot.transactions[0]
    assert (tx.transaction_id, tx.date, tx.debit, tx.credit) == (
        "tx-1",
        date(2026, 10, 1),
        1200.0,
        None,
    )


def test_authorize_cached_body() -> None:
    """C28: every read is the cached one, authorized with a fresh token."""
    client, recorder, _ = mock_client(flinks_api())

    client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)

    assert recorder.body("Authorize") == {"LoginId": LOGIN_ID, "MostRecentCached": True}
    authorize = next(r for r in recorder.requests if r.url.path.endswith("/Authorize"))
    assert authorize.headers["flinks-auth-key"] == "token-1"
    token = next(
        r for r in recorder.requests if r.url.path.endswith("/GenerateAuthorizeToken")
    )
    assert token.headers["flinks-auth-key"] == "auth-key-secret"


def sentry_events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """The app's own Sentry init, delivering to a list (frame locals included)."""
    import sentry_sdk
    from sentry_sdk.envelope import Envelope
    from sentry_sdk.transport import Transport

    from app import monitoring
    from app.settings import get_settings

    events: list[dict[str, object]] = []

    class Capture(Transport):
        def capture_envelope(self, envelope: Envelope) -> None:
            event = envelope.get_event()
            if event is not None:
                events.append(dict(event))

    real_init = sentry_sdk.init
    monkeypatch.setattr(
        monitoring.sentry_sdk,
        "init",
        lambda *a, **k: real_init(*a, transport=Capture(), **k),
    )
    settings = get_settings().model_copy(
        update={"sentry_dsn": "https://public@sentry.example.invalid/1"}
    )
    assert monitoring.init_sentry(settings)
    return events


def test_sentry_event_carries_no_flinks_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C20 (Sentry): an unexpected error inside a Flinks call, and a malformed answer,
    reach Sentry without the loginId, the keys, the account number or the holder."""
    import sentry_sdk

    events = sentry_events(monkeypatch)
    try:

        def explode(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/GetAccountsDetail"):
                raise RuntimeError("unexpected")
            return flinks_api()(request)

        client, _, _ = mock_client(explode)
        with pytest.raises(RuntimeError):
            client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)
        sentry_sdk.capture_exception()

        broken = json.loads(json.dumps(DETAIL))
        del broken["Accounts"][0]["Id"]

        def malformed(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/GetAccountsDetail"):
                return httpx.Response(200, json=broken)
            return flinks_api()(request)

        client, _, _ = mock_client(malformed)
        with pytest.raises(FlinksError) as raised:
            client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)
        assert raised.value.flinks_code == "INVALID_RESPONSE"
        assert raised.value.__suppress_context__
        sentry_sdk.capture_exception(raised.value)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    assert len(events) == 2
    serialized = json.dumps(events, default=str)
    assert '"vars"' in serialized  # frame locals were sent, and redacted
    for secret in (
        LOGIN_ID,
        "auth-key-secret",
        "api-key-secret",
        "token-1",
        "00012345678901",
        "Dana Holder",
    ):
        assert secret not in serialized, secret


def test_last_refresh_accepts_slash_dates() -> None:
    """F2: `LastRefresh` in Flinks' yyyy/MM/dd form still parses."""
    detail = json.loads(json.dumps(DETAIL))
    detail["Login"]["LastRefresh"] = "2026/10/15 07:30:00"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/GetAccountsDetail"):
            return httpx.Response(200, json=detail)
        return flinks_api()(request)

    client, _, _ = mock_client(handler)
    snapshot = client.accounts(LOGIN_ID, with_transactions=True, days="Days90", polls=3)

    assert snapshot.last_refresh is not None
    assert snapshot.last_refresh.isoformat() == "2026-10-15T07:30:00+00:00"


def test_missing_institution_id_is_not_the_name() -> None:
    """F4: no InstitutionId means no institution, never the display name."""
    detail = json.loads(json.dumps(DETAIL))
    del detail["InstitutionId"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/GetAccountsDetail"):
            return httpx.Response(200, json=detail)
        return flinks_api()(request)

    client, _, _ = mock_client(handler)
    snapshot = client.accounts(
        LOGIN_ID, with_transactions=False, days="Days90", polls=3
    )

    assert snapshot.institution_id == ""


def test_delete_card_login_id_redacted_in_any_form() -> None:
    """F5: the loginId after `DeleteCard/` is redacted with or without a leading slash, as
    a frame's `path` local or in httpx's request line."""
    from app.log import redact

    redacted = redact(
        {
            "path": f"DeleteCard/{LOGIN_ID}",
            "url": f"https://toolbox-api.private.fin.ag{BASE}/DeleteCard/{LOGIN_ID}",
        }
    )

    assert LOGIN_ID not in json.dumps(redacted)


def test_sentry_event_from_delete_carries_no_login_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F5: an unexpected error during DeleteCard reaches Sentry without the loginId."""
    import sentry_sdk

    events = sentry_events(monkeypatch)
    try:

        def explode(request: httpx.Request) -> httpx.Response:
            raise RuntimeError("unexpected")

        client, _, _ = mock_client(explode)
        try:
            client.delete(LOGIN_ID)
        except RuntimeError as error:
            sentry_sdk.capture_exception(error)
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_global_scope().set_client(None)

    serialized = json.dumps(events, default=str)
    assert len(events) == 1 and '"vars"' in serialized
    assert LOGIN_ID not in serialized
    assert "api-key-secret" not in serialized
