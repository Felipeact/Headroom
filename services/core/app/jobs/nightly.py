"""Spec 15: sync every bank once a night, around 2 AM in its business's time zone."""

import dataclasses
from datetime import datetime

from app.modules.bank_sync import service
from app.modules.bank_sync.flinks import get_flinks_client
from app.modules.bank_sync.plaid import get_plaid_client


def nightly_bank_sync(now: datetime) -> dict[str, int]:
    """Run the nightly syncs due at `now`; returns the counts for `jobs.run_finished`."""
    return dataclasses.asdict(
        service.run_nightly_syncs(get_plaid_client(), now, get_flinks_client())
    )
