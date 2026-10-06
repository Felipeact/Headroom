# Spec 17: Bank connection settings

- **Milestone:** 3, bank data
- **Status:** Done
- **Depends on:** 13, 14

## Goal

Let owners manage their bank connections after onboarding.

## Build

- A settings page matching `settings-banks.dc.html`. For each bank, it shows the sync status and the accounts, with switches to include or exclude each account, a choice of primary account, and a disconnect button.
- Repairing a connection that needs attention uses Plaid Link's update mode.
- Disconnecting removes the connection at Plaid, deletes the stored token, stops syncing, and writes an audit log entry.
- The settings navigation: Business, Bank connections, Members, Email preferences, and Your data. Sections without a spec yet show a placeholder.

## Done when

- [x] A sandbox connection forced into a "login required" state shows the banner, and can be repaired.
- [x] After a disconnect, syncing stops and the token is gone.
