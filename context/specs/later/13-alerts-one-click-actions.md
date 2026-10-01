# Spec 13: One-click actions

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 2 (paid pilot)
- **Status:** Not started
- **Modules:** `alerts`, `notifications`
- **Depends on:** 06, 08, [11](11-integrations-quickbooks-and-xero.md)

## Goal

Turn a suggested fix into something the owner can do in one click. The first action is asking a client to pay early.

## Requirements

1. When a suggested fix involves money a client owes, the alert shows an "Ask to pay early" button.
2. The button opens a pre-filled email with the client's name, the invoice, the amount, and an optional early-payment discount (for example, 2% if paid within 5 days). The owner can edit the email, and nothing is sent until they click Send.
3. The email is sent from the product's domain on the business's behalf, and replies go to the owner. The sending domain must have SPF and DKIM set up, so emails aren't marked as spam.
4. The client's email address comes from the accounting data in [spec 11](11-integrations-quickbooks-and-xero.md), or the owner types it in.
5. Each action is tracked as drafted, sent, or succeeded. It counts as succeeded when the client pays early. These statuses feed the "alerts that lead to an action" metric.
6. A business can send the same client at most 3 reminders a week.
7. One-click actions are included only in the Growth plan.

## Out of scope

Other actions, such as asking a supplier for more time or referring the owner to a financing partner. They belong in a later spec.

## Acceptance criteria

- [ ] Starting from the week-7 example, an owner can send an early-payment request in under 1 minute.
- [ ] Nothing is sent until the owner clicks Send on the preview.
- [ ] A client's reply reaches the owner's inbox.
- [ ] When an early payment arrives, it's linked to the action, and the action is marked as succeeded.
- [ ] A fourth reminder to the same client in one week is blocked.
