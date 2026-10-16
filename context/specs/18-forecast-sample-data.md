# Spec 18: Sample data

- **Milestone:** 4, forecast
- **Status:** Done
- **Depends on:** 14

## Goal

Create a synthetic business for tests, demos, and backtests, so nothing ever needs real data.

## Build

- `app/fixtures/harbor_street.py` generates Harbor Street Plumbing, dated from a fixed reference day of Saturday, September 26, 2026:
  - two banks
  - operating checking with $8,000, and reserve savings with $34,300
  - a Business Visa card with a $2,450 payment due Oct 8
  - a line of credit with $20,000 available
  - 18 months of history: payroll every two weeks, monthly rent, supplier bills, client payments, card payments, and transfers between the two accounts
  - the cash gap from the alert mockup: a low of $3,150 in the week of Nov 9, caused by Coastal Supply Co ($14,500) and payroll ($11,200), with Birch & Co's $9,600 arriving after it
- `uv run python -m app.fixtures.load harbor_street` loads it into a local database.

## Done when

- [x] Generating the data twice with the same seed gives identical results.
- [x] Once loaded, the sample business's accounts and transactions are available through the API.
