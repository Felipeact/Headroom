# Spec 11: Businesses and access

- **Milestone:** 2, foundations
- **Status:** Not started
- **Depends on:** 10

## Goal

Let a signed-in owner create their business, and keep every business's data separate.

## Build

- **API:**
  - A `businesses` table: name, province, and time zone. The country is Canada and the currency is CAD.
  - A `memberships` table: user, business, and role. In this spec the only role is owner.
  - `require_member(business_id, roles)`: every business endpoint uses it. A business the user doesn't belong to returns 404.
  - `POST /v1/businesses`, plus `GET` and `PATCH /v1/businesses/{business_id}`.
  - Quebec is refused with a clear message.
- **Web:**
  - Onboarding step 2, matching `onboarding-2-business.dc.html`.
  - A signed-in user without a business always lands on this step.

## Done when

- [ ] A new user can create a business in under 2 minutes.
- [ ] Every business endpoint returns 404 for a business the user doesn't belong to (tested).
- [ ] Choosing Quebec shows the "not available yet" message.
