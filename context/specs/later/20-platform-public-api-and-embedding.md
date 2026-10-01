# Spec 20: Public API and embedded forecasting

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 4 (scale)
- **Status:** Not started
- **Area:** Platform
- **Depends on:** 05, 06, [14](14-firm-multi-client-workspace.md), [17](17-platform-forecast-workers-and-observability.md)

## Goal

Let accounting firms, payroll and bookkeeping software, and other partners read forecasts and alerts through an API, and show the forecast inside their own products.

## Requirements

1. **Public API.** The public API is separate from the API the dashboard uses.
   - It's documented with an OpenAPI schema and has version numbers.
   - An old version is removed only after at least 12 months' notice.
2. **Authentication:**
   - Partner apps use OAuth 2.0 to act on a business's behalf. The owner sees a consent screen and approves specific permissions (scopes), such as `forecast:read` and `alerts:read`.
   - Firms can create API keys for their own tools. Each key is shown once, stored only as a hash, and can be revoked.
3. **Permissions.** Each scope grants only the access it needs. At first, the API is read-only.
4. **Webhooks to partners.** Partners can receive `forecast.updated` and `alert.created` events as webhooks.
   - Each webhook is signed with HMAC, so partners can verify it came from us.
   - Failed deliveries are retried.
   - Partners can see a log of deliveries.
5. **Limits and metering.** Each partner has rate limits. Usage is measured, in case API access is priced later.
6. **Embedded forecast.** A ready-made component shows the forecast inside a partner's app. It authenticates with short-lived tokens that the partner's backend requests.
7. **Partner sandbox.** Partners can build and test against a sandbox filled with synthetic data.

## Acceptance criteria

- [ ] A partner app completes OAuth in the sandbox, and can read a forecast using only the scopes it was granted.
- [ ] Partners can verify webhook signatures by following the documentation.
- [ ] Revoking consent stops the partner's access immediately.
- [ ] API documentation is generated from the schema and published.
- [ ] A partner that exceeds its rate limit gets a 429 response with a `Retry-After` header.
