# Later: build after the first clients confirm

These features wait until the pilot gate in `Roadmap.md` passes. The detailed drafts in this folder were written before the specs were restructured for parallel work.

Before building one, split it into short specs in the same format as specs 01–36. Each new spec covers one piece, and lists its dependencies, the docs it needs, and what "done" means.

## Priority order

| # | Feature | Draft |
|---|---|---|
| 1 | Billing and plan limits in the app, replacing the manual Stripe Payment Links | [09-billing-subscriptions-and-plans.md](09-billing-subscriptions-and-plans.md) |
| 2 | Alerts for a single account running short, with the fix of moving money between accounts | Decisions below |
| 3 | QuickBooks and Xero sync | [11-integrations-quickbooks-and-xero.md](11-integrations-quickbooks-and-xero.md) |
| 4 | French and Quebec: the app and emails in French, plus Quebec's privacy law (Law 25), which requires an assessment before Quebec data is stored outside the province | No draft yet |
| 5 | Scenarios, and correcting detected patterns | [12-forecasting-scenarios-and-corrections.md](12-forecasting-scenarios-and-corrections.md) |
| 6 | One-click actions | [13-alerts-one-click-actions.md](13-alerts-one-click-actions.md) |
| 7 | Workspace for accounting firms | [14-firm-multi-client-workspace.md](14-firm-multi-client-workspace.md) |
| 8 | Industry templates | [15-forecasting-industry-templates.md](15-forecasting-industry-templates.md) |
| 9 | Public launch, free forecast check, and referrals | [16-growth-public-launch-and-referrals.md](16-growth-public-launch-and-referrals.md) |
| 10 | Separate forecast workers, a message queue, and monitoring | [17-platform-forecast-workers-and-observability.md](17-platform-forecast-workers-and-observability.md) |
| 11 | Penetration test and SOC 2 | [18-security-pentest-and-soc2.md](18-security-pentest-and-soc2.md) |
| 12 | Multiple currencies (US-dollar accounts at Canadian banks first, then US businesses), legal entities, and regions | [19-platform-multi-currency-and-entities.md](19-platform-multi-currency-and-entities.md) |
| 13 | Public API, and forecasts shown inside partners' apps | [20-platform-public-api-and-embedding.md](20-platform-public-api-and-embedding.md) |
| 14 | Benchmarking and anomaly detection | [21-insights-benchmarking-and-anomalies.md](21-insights-benchmarking-and-anomalies.md) |
| 15 | Split into services and move to Kubernetes, only if Railway stops being enough | [22-platform-kubernetes-and-service-split.md](22-platform-kubernetes-and-service-split.md) |

## Smaller items cut from v1

- CSV import of invoices and bills
- predicting card payments from the card's statement balance and due date
- plain-language alert wording from an LLM, checked against the forecast data
- the "stagger payments" fix
- the account picker on the forecast chart
- automated data deletion

## Decisions already made for single-account alerts

- Forecast each included account day by day for the next 14 days, so an overdraft in the middle of a week isn't hidden.
- Alert when one account is projected to go below $0 while the combined balance stays above the minimum.
- Suggest moving money from an account that has spare money. The amount is the shortfall plus a $1,000 buffer, rounded up to the nearest $1,000. The account the money comes from must not run short itself.
- Suggest a deadline of 1 business day before the payment when both accounts are at the same bank, and 2 business days when they're at different banks.
