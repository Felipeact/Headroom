# Spec 14: Firm workspace for accountants

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 3 (launch and grow)
- **Status:** Not started
- **Modules:** `accounts`, `billing`, `frontend`
- **Depends on:** 01, 07, [09](09-billing-subscriptions-and-plans.md)

## Goal

Let bookkeeping and accounting firms manage many client businesses from one login, and bill the firm for each client.

## Requirements

1. **Firms.** A firm has a name, members (firm admins and firm staff), and links to client businesses.
2. **Access grants.** A firm gets access to a business through a grant.
   - Either the firm or the business can request a grant, but the business owner must approve it.
   - The owner can revoke a grant at any time, and the revocation takes effect immediately.
3. **Assignments.** Firm admins assign clients to staff, and staff see only their assigned clients.
4. **Client overview.** One list shows all of a staff member's clients. For each client it shows:
   - cash on hand
   - the lowest projected balance
   - open alerts
   - the status of the last sync

   The list is sorted by risk by default, with the soonest and largest cash gaps first.
5. **Firm digest.** Firm staff get one digest email covering all their clients, instead of one email per client.
6. **Firm billing:**
   - The firm pays $15–20 per client per month. The price is set in Stripe.
   - Businesses covered by a firm plan don't pay separately.
   - The number of active clients is counted each month.
7. **Read-only advisor role.** A business can invite an advisor or investor who can see everything but change nothing.
8. **Audit log.** Every grant, revocation, and firm access to client data is recorded.

## Acceptance criteria

- [ ] For a firm with 30 clients, the overview loads in under 2 seconds.
- [ ] Once a grant is revoked, the firm's next request for that client is denied (tested).
- [ ] Firm staff can't see clients who aren't assigned to them (tested).
- [ ] The firm's monthly invoice matches its number of active clients.
- [ ] A read-only advisor gets a 403 error from every endpoint that changes data.
