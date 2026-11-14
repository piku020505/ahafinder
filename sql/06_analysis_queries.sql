-- 06_analysis_queries.sql
-- Named queries used by src/analyze.py. Each block starts with "-- name: <query_name>".

-- name: funnel_overall
SELECT 'app_install'   AS step, 1 AS step_no, count(*)            AS users FROM mart_user_activation
UNION ALL SELECT 'signup_completed', 2, sum(did_signup)    FROM mart_user_activation
UNION ALL SELECT 'kyc_started',      3, sum(did_kyc_start) FROM mart_user_activation
UNION ALL SELECT 'kyc_completed',    4, sum(did_kyc_done)  FROM mart_user_activation
UNION ALL SELECT 'upi_linked',       5, sum(did_upi)       FROM mart_user_activation
UNION ALL SELECT 'first_purchase',   6, sum(did_first_buy) FROM mart_user_activation
ORDER BY step_no;

-- name: kyc_by_device_tier
SELECT device_segment, city_tier,
       sum(did_kyc_start)                                    AS kyc_starters,
       sum(did_kyc_done)                                     AS kyc_completers,
       round(sum(did_kyc_done) * 1.0 / sum(did_kyc_start), 4) AS kyc_completion_rate
FROM mart_user_activation
WHERE did_kyc_start = 1
GROUP BY 1, 2 ORDER BY 1, 2;

-- name: kyc_fail_reasons
SELECT device_segment, first_kyc_fail_reason AS reason, count(*) AS users
FROM mart_user_activation
WHERE kyc_fail_count > 0
GROUP BY 1, 2 ORDER BY 1, 3 DESC;

-- name: activation_by_channel
SELECT channel,
       count(*)                                                     AS installs,
       round(avg(did_first_buy), 4)                                 AS install_to_first_buy,
       round(avg(CASE WHEN did_first_buy = 1 THEN d30_retained END), 4) AS d30_retention_of_buyers
FROM mart_user_activation
GROUP BY 1 ORDER BY 3 DESC;

-- name: retention_curve_buyers
-- share of first-time buyers who opened the app on each day since install
WITH buyers AS (SELECT user_id FROM mart_user_activation WHERE did_first_buy = 1),
opens AS (
    SELECT DISTINCT e.user_id, e.day_n
    FROM stg_events e JOIN buyers b USING (user_id)
    WHERE e.event_name = 'app_open' AND e.day_n BETWEEN 1 AND 34
)
SELECT day_n, count(*) * 1.0 / (SELECT count(*) FROM buyers) AS pct_active
FROM opens GROUP BY 1 ORDER BY 1;

-- name: time_to_convert
SELECT
    quantile_cont(mins_install_to_signup, 0.5)  AS median_mins_install_to_signup,
    quantile_cont(mins_kyc_start_to_done, 0.5)  AS median_mins_kyc,
    quantile_cont(hrs_install_to_first_buy, 0.5) AS median_hrs_to_first_buy,
    quantile_cont(hrs_install_to_first_buy, 0.9) AS p90_hrs_to_first_buy
FROM mart_user_activation;
