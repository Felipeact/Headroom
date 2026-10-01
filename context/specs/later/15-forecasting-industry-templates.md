# Spec 15: Industry templates

> **Backlog draft.** This was written before the specs were restructured for parallel work, so its spec numbers and "Depends on" line use the old numbering. Before building it, split it into short specs in the current format (see [README.md](README.md)).

- **Phase:** 3 (launch and grow)
- **Status:** Not started
- **Module:** `forecasting`
- **Depends on:** 04, 05

## Goal

Give new businesses useful forecasts from day one, by starting from patterns that are typical for their industry.

## Requirements

1. Build templates for 2–3 industries, choosing the industries where most pilot customers came from.
2. Each template describes, for its industry:
   - typical recurring costs and their schedules, such as payroll, rent, insurance, and supplier bills
   - how late customers usually pay
   - seasonal patterns
3. During onboarding, the owner picks an industry. The template then suggests recurring items, and the owner confirms or dismisses each one. Suggestions are never added without the owner's confirmation.
4. Templates are built only from public information, or from anonymized data combined across at least 20 businesses. A template must never reveal data from any single business.
5. As a business builds up real history, the patterns detected from that history replace the template's suggestions.

## Acceptance criteria

- [ ] A new business in an industry that has a template sees suggested items during onboarding, and can confirm them in under 2 minutes.
- [ ] When tested on past data, businesses with less than 4 weeks of history get more accurate 4-week forecasts with a template than without one.
- [ ] A template can't be generated from fewer than 20 businesses (tested).
