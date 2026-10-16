"""Spec 34 door 5: staging and production share no credentials.

Reads every variable of `api`, `web` and `jobs` in both Railway environments through
`railway variable list --json` (rendered values) and fails on any name whose value is the
same in both, unless the name is a known non-secret setting. Prints names, never values.
Exit 0: nothing shared. Exit 1: something shared, or a service could not be read.
"""

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping

SERVICES = ("api", "web", "jobs")
ENVIRONMENTS = ("staging", "production")

# Settings that are the same everywhere and open nothing. A new name is a secret until
# it is added here, so a credential added later fails by default.
ALLOWED = frozenset(
    {
        "NEXT_PUBLIC_CLERK_SIGN_IN_URL",
        "NEXT_PUBLIC_CLERK_SIGN_UP_URL",
        "POSTHOG_HOST",
        "POSTHOG_APP_HOST",
        "EMAIL_MAILING_ADDRESS",
        "FORECAST_STRATEGY",
        # A mode (`resend` or `console`), not a credential (plan door 10).
        "EMAIL_SENDER",
        # Temporary (plan door 11): one PostHog project until production gets its own.
        "POSTHOG_KEY",
        "POSTHOG_PROJECT_ID",
        # Plaid issues one client ID per team for every environment; the secret differs.
        "PLAID_CLIENT_ID",
    }
)
ALLOWED_PREFIX = "RAILWAY_"

Variables = Mapping[str, str]
Reader = Callable[[str, str], Variables]


class ReadError(Exception):
    def __init__(self, service: str, environment: str, detail: str) -> None:
        super().__init__(f"cannot read {service} in {environment} ({detail})")


def read_railway(service: str, environment: str) -> Variables:
    exe = shutil.which("railway")
    if exe is None:
        raise ReadError(service, environment, "railway CLI not found")
    result = subprocess.run(
        [exe, "variable", "list", "--service", service, "--environment", environment,
         "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    # Never echo the CLI's output: it holds raw values.
    if result.returncode != 0:
        raise ReadError(service, environment, f"railway exited {result.returncode}")
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise ReadError(service, environment, "output is not JSON") from None
    if not isinstance(data, dict):
        raise ReadError(service, environment, "output is not an object")
    return {str(k): str(v) for k, v in data.items()}


def shared(variables: Mapping[tuple[str, str], Variables]) -> list[tuple[str, str]]:
    """`(service, NAME)` for every non-allowed name equal in staging and production."""
    found = []
    for service in SERVICES:
        staging = variables[(service, "staging")]
        production = variables[(service, "production")]
        for name in sorted(staging.keys() & production.keys()):
            if name in ALLOWED or name.startswith(ALLOWED_PREFIX):
                continue
            if staging[name] == production[name]:
                found.append((service, name))
    return found


def main(read: Reader = read_railway) -> int:
    try:
        variables = {
            (service, env): read(service, env)
            for service in SERVICES
            for env in ENVIRONMENTS
        }
    except ReadError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    matches = shared(variables)
    for service, name in matches:
        print(f"{service} {name}")
    if matches:
        print(f"FAIL: {len(matches)} shared", file=sys.stderr)
        return 1
    print("PASS: staging and production share no credentials")
    return 0


if __name__ == "__main__":
    sys.exit(main())
