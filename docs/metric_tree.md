# Metric tree

```
North Star: Weekly Active Savers (WAS)
   users with >= 1 successful saving (manual buy or AutoSave debit) in the week
│
├── New savers  = installs × install→first-buy rate (31.1%)
│     ├── signup rate                      75%
│     ├── KYC start rate                   72%
│     ├── KYC completion rate              90%   ← low-end Android 73.5% vs 94.0% for everyone else
│     ├── UPI link rate                    84%
│     └── first-buy rate                   76%
│
├── Retained savers = new savers × D30 retention (47.3% of first-time buyers)
│     ├── aha reached in week 1            63.0% of buyers
│     │     ├── AutoSave adoption          38.0%
│     │     └── 3+ manual buys             44.9%
│     └── D30 retention | aha vs no aha    63.3% vs 20.1%
│
└── Saving reliability (guardrail)
      └── AutoSave debit failure rate      7.0%
```

**How to read it.** WAS rises only through new savers (fix the funnel) or retained savers (get more users to the aha moment). The analysis says the cheapest levers are:
1. **KYC on low-end Android.** One segment produces half of all KYC failures.
2. **AutoSave set-up right after the first purchase.** It's the strongest adjusted predictor of D30 retention, and it's a single screen the product team controls.

**Guardrail.** A 7.0% AutoSave debit failure rate caps how much AutoSave can help. If mandate failures rise when adoption is pushed, WAS will not grow as much as adoption does.
