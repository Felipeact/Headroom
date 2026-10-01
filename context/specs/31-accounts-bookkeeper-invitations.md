# Spec 31: Bookkeeper invitations

- **Milestone:** 6, emails and bookkeepers
- **Status:** Not started
- **Depends on:** 11, 28

## Goal

Let owners bring in their bookkeeper, with limited permissions.

## Build

- **Invitations:**
  - Owners invite a bookkeeper by email, and the link expires after 7 days.
  - Accepting the invitation, while signed in with the invited email address, adds a bookkeeper membership.
  - Owners can remove members.
  - Each of these actions writes an audit log entry.
- **Bookkeeper permissions:**
  - Bookkeepers can view forecasts and alerts, and manage expected payments.
  - They can't change banks, members, or business settings. The API enforces this, and the web app hides those controls.
- **Web:** the Members section of settings, and the `/invite/[token]` page.

## Done when

- [ ] Bookkeepers get 403 from every owner-only endpoint (tested).
- [ ] An expired invitation can't be accepted.
