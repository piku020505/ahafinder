-- 05_mart_user_activation.sql
-- Analysis-ready mart: one row per user with attributes, funnel flags, week-1 behaviour, retention.

CREATE OR REPLACE TABLE mart_user_activation AS
SELECT
    u.*,
    (f.signup_ts    IS NOT NULL)::INT AS did_signup,
    (f.kyc_start_ts IS NOT NULL)::INT AS did_kyc_start,
    (f.kyc_done_ts  IS NOT NULL)::INT AS did_kyc_done,
    (f.upi_ts       IS NOT NULL)::INT AS did_upi,
    (f.first_buy_ts IS NOT NULL)::INT AS did_first_buy,
    f.kyc_fail_count,
    f.first_kyc_fail_reason,
    epoch(f.signup_ts    - u.install_ts) / 60.0   AS mins_install_to_signup,
    epoch(f.kyc_done_ts  - f.kyc_start_ts) / 60.0 AS mins_kyc_start_to_done,
    epoch(f.first_buy_ts - u.install_ts) / 3600.0 AS hrs_install_to_first_buy,
    w.* EXCLUDE (user_id),
    r.* EXCLUDE (user_id)
FROM stg_users u
JOIN int_user_funnel     f USING (user_id)
JOIN int_week1_behaviour w USING (user_id)
JOIN int_retention       r USING (user_id);
