"""Events the bank_sync module publishes (AD-048)."""

# After a sync that changed a transaction or a balance. Payload: `connection_id` (str),
# `added`, `modified`, `removed` (int), `balances_changed` (bool).
TRANSACTIONS_SYNCED = "transactions.synced"
