# Spec 29: Alert emails

- **Milestone:** 6, emails and bookkeepers
- **Status:** Done
- **Depends on:** 25, 28

## Goal

Email the owner when a cash gap appears or gets worse.

## Build

- When `alert.created` or `alert.updated` arrives, email the owners, and any bookkeepers who opted in, using `email-alert.dc.html`.
  - Note (2026-10-13): bookkeepers don't exist until spec 31, so this spec emails owners only. Spec 31 adds bookkeepers who opt in, through the same recipient query (AD-116).

## Done when

- [x] The email matches its mockup, and displays correctly in Gmail, Outlook, and Apple Mail.
  - Note (2026-10-14): checked by the user in all three; only the Gmail screenshot is saved (AD-117).
- [x] No email contains a full account number or a link that logs someone in automatically.
