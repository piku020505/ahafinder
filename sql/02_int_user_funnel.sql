-- 02_int_user_funnel.sql
-- One row per user with the first timestamp of each onboarding step.

CREATE OR REPLACE TABLE int_user_funnel AS
SELECT
    u.user_id,
    u.install_ts,
    min(CASE WHEN event_name = 'signup_completed' THEN event_ts END)                       AS signup_ts,
    min(CASE WHEN event_name = 'kyc_started'      THEN event_ts END)                       AS kyc_start_ts,
    min(CASE WHEN event_name = 'kyc_completed'    THEN event_ts END)                       AS kyc_done_ts,
    min(CASE WHEN event_name = 'upi_linked'       THEN event_ts END)                       AS upi_ts,
    min(CASE WHEN event_name = 'gold_purchased'   THEN event_ts END)                       AS first_buy_ts,
    count(CASE WHEN event_name = 'kyc_failed' THEN 1 END)                                  AS kyc_fail_count,
    arg_min(CASE WHEN event_name = 'kyc_failed' THEN kyc_fail_reason END,
            CASE WHEN event_name = 'kyc_failed' THEN event_ts END)                         AS first_kyc_fail_reason
FROM stg_users u
LEFT JOIN stg_events e USING (user_id)
GROUP BY 1, 2;
