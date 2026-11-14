# Tracking plan: Sona (event dictionary)

Each event carries `event_id`, `user_id`, `event_ts` (UTC), `platform`, and a JSON `properties` blob.
An analyst should be able to answer every funnel and retention question from these 15 events.

| # | Event | Fired when | Key properties | Used for |
|---|---|---|---|---|
| 1 | `app_install` | First app launch after install | `channel` | Funnel top, acquisition mix |
| 2 | `signup_completed` | Phone OTP verified and profile created | - | Funnel step 2 |
| 3 | `kyc_started` | User opens the KYC flow | - | Funnel step 3 |
| 4 | `kyc_failed` | A KYC attempt is rejected | `attempt`, `reason` (`selfie_liveness_fail`, `pan_name_mismatch`, `aadhaar_otp_timeout`) | KYC failure diagnosis |
| 5 | `kyc_completed` | KYC approved | `attempt` | Funnel step 4 |
| 6 | `upi_linked` | UPI handle verified | - | Funnel step 5 |
| 7 | `gold_purchased` | A buy order settles | `amount` (INR), `source` (`manual`) | First purchase (activation), week-1 buy count |
| 8 | `autosave_enabled` | User sets up a daily AutoSave mandate | `daily_amount` | Aha candidate |
| 9 | `autosave_debit_success` | Daily mandate debit succeeds (system event) | - | North Star (saving activity), **excluded** from retention |
| 10 | `autosave_debit_failed` | Daily mandate debit fails | - | Payment reliability guardrail |
| 11 | `autosave_cancelled` | User cancels AutoSave | - | Churn signal |
| 12 | `goal_created` | User creates a savings goal | `goal_type` | Aha candidate |
| 13 | `price_alert_set` | User sets a gold-price alert | - | Aha candidate |
| 14 | `referral_sent` | User shares a referral link | - | Aha candidate |
| 15 | `app_open` | App comes to foreground (de-duplicated per session) | - | Retention (D7, D30) |

## Metric definitions

| Metric | Definition |
|---|---|
| Activation | First `gold_purchased` within 7 days of `app_install` |
| D7 / D30 retention | At least one `app_open` on days 7-13 / days 28-34 after install. System events (AutoSave debits) never count, otherwise autopay would inflate retention. |
| KYC completion rate | Users with `kyc_completed` / users with `kyc_started` |
| Aha moment | AutoSave enabled **or** 3+ manual buys within 7 days of install (see README for how this was chosen) |
| AutoSave debit failure rate | `autosave_debit_failed` / all AutoSave debit attempts |

## Instrumentation notes
- `day_n` (days since install) is derived in `sql/01_staging.sql` as 24-hour buckets from the install timestamp, not calendar days. This avoids a user who installs at 11:59 pm being counted as "day 1" a minute later.
- `kyc_failed.reason` is the single most valuable property here. Without it, the low-end Android selfie problem would look like a generic KYC drop-off.
