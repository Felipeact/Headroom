# Spec 16: Transaction labels

- **Milestone:** 3, bank data
- **Status:** In progress
- **Depends on:** 14

## Goal

Label each transaction, so transfers and credit card activity don't distort the forecast.

## Build

Give every transaction one of these labels:

- **Internal transfer:** the same amount leaves one of the business's accounts and arrives in another within 3 business days. Link the two halves.
- **In transit:** an outgoing transfer whose other half hasn't arrived yet. If nothing matches after 3 business days, it becomes normal.
- **Card purchase** and **card payment.**
- **Credit draw** and **credit repayment.**
- **Normal:** everything else.

## Done when

- [ ] A $10,000 transfer from savings to checking is labeled an internal transfer on both sides.
- [ ] Card purchases and card payments get the right labels.
- [ ] A transfer with no match becomes normal after 3 business days.
