# Spec 28: Email foundation

- **Milestone:** 6, emails and bookkeepers
- **Status:** In progress
- **Depends on:** 10

## Goal

Set up reliable email sending, and the preferences and unsubscribe link every email needs.

## Build

- Resend sits behind an `EmailSender` interface. A console sender prints emails when running locally.
- A base email template that follows `DESIGN.md`:
  - 600px wide, with the wordmark at the top
  - a footer saying why the person gets the email, with links to email preferences and to unsubscribe, and the mailing address
  - a plain-text version of every email
- `GET` and `PUT /v1/me/email-preferences`.
- `POST /v1/unsubscribe/{token}` unsubscribes in one click, without logging in.
- Each event sends at most one email per recipient. Failed sends are retried.

**Docs:** [Resend](https://resend.com/docs)

## Done when

- [ ] When the same event is processed twice, only one email is sent.
- [ ] Unsubscribing works without logging in, and takes effect immediately.
- [ ] When the email provider fails, the send is retried until it succeeds.
