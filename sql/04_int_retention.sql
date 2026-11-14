-- 04_int_retention.sql
-- Retention = user opened the app at least once inside the window (user-initiated activity only;
-- automatic AutoSave debits do NOT count, otherwise retention would be inflated by autopay).
--   D7  window: days 7-13      D30 window: days 28-34

CREATE OR REPLACE TABLE int_retention AS
SELECT
    u.user_id,
    max(CASE WHEN event_name = 'app_open' AND day_n BETWEEN 7  AND 13 THEN 1 ELSE 0 END) AS d7_retained,
    max(CASE WHEN event_name = 'app_open' AND day_n BETWEEN 28 AND 34 THEN 1 ELSE 0 END) AS d30_retained,
    max(CASE WHEN event_name = 'autosave_cancelled' THEN 1 ELSE 0 END)                   AS autosave_cancelled,
    count(CASE WHEN event_name = 'autosave_debit_failed' THEN 1 END)                     AS autosave_failed_debits,
    count(CASE WHEN event_name = 'autosave_debit_success' THEN 1 END)                    AS autosave_success_debits
FROM stg_users u
LEFT JOIN stg_events e USING (user_id)
GROUP BY 1;
