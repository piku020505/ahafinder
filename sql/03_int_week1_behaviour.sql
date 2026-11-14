-- 03_int_week1_behaviour.sql
-- What each user did in their first 7 days (day_n 0..6). These are the candidate "aha" actions.

CREATE OR REPLACE TABLE int_week1_behaviour AS
SELECT
    u.user_id,
    count(CASE WHEN event_name = 'gold_purchased' AND purchase_source = 'manual' AND day_n <= 6 THEN 1 END) AS w1_manual_buys,
    coalesce(sum(CASE WHEN event_name = 'gold_purchased' AND day_n <= 6 THEN amount_inr END), 0)            AS w1_buy_value_inr,
    max(CASE WHEN event_name = 'autosave_enabled' AND day_n <= 6 THEN 1 ELSE 0 END)                         AS w1_autosave,
    max(CASE WHEN event_name = 'goal_created'     AND day_n <= 6 THEN 1 ELSE 0 END)                         AS w1_goal,
    max(CASE WHEN event_name = 'price_alert_set'  AND day_n <= 6 THEN 1 ELSE 0 END)                         AS w1_price_alert,
    max(CASE WHEN event_name = 'referral_sent'    AND day_n <= 6 THEN 1 ELSE 0 END)                         AS w1_referral,
    count(DISTINCT CASE WHEN event_name = 'app_open' AND day_n BETWEEN 1 AND 6 THEN day_n END)              AS w1_active_days
FROM stg_users u
LEFT JOIN stg_events e USING (user_id)
GROUP BY 1;
