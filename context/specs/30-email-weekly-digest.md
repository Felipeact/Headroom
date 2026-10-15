# Spec 30: Weekly digest

- **Milestone:** 6, emails and bookkeepers
- **Status:** In progress
- **Depends on:** 15, 21, 28

## Goal

Send a weekly summary, so most weeks owners don't need to log in at all.

## Build

- A job sends the digest on Mondays during the 8 AM hour in each business's time zone, which means 8:30 in Newfoundland. It follows `email-digest.dc.html`.
- When there are no gaps, the digest still goes out, with a short "all clear" message.

## Done when

- [ ] With a simulated clock, digests arrive on time in Pacific, Eastern, and Newfoundland time.
- [ ] The email matches its mockup.
