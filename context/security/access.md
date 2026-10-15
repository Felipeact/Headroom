# Who can reach production

Spec 33. One row per person per service. Everyone with access has two-factor authentication on,
and nobody has access without a reason. Re-check every 90 days: `tests/test_security_rules.py::test_access_table_complete`
fails when a date is older.

Fill in each row from the service's own members page, not from memory. Columns: service, person,
role held, reason, two-factor on (`yes` or `no`), date checked (ISO).

| Service | Person | Role | Reason | 2FA | Checked |
| --- | --- | --- | --- | --- | --- |
| Clerk | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| Railway | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| GitHub | Felipe Viana | Owner | runs the product; the only person with access | yes | 2026-10-15 |
| Resend | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| PostHog | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| Sentry | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| Plaid | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |
| Domain registrar | Felipe Viana | Owner | runs the product; the only person with access | no | 2026-10-15 |

Only Felipe Viana has production access. Seven accounts have no two-factor authentication yet; turn it on in each service, then change that row's 2FA to `yes` and its date.
