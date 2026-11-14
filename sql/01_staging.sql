-- 01_staging.sql
-- Clean, typed views over the raw parquet files. One row per user / per event.

CREATE OR REPLACE VIEW stg_users AS
SELECT
    user_id,
    CAST(install_ts AS TIMESTAMP)              AS install_ts,
    CAST(install_ts AS DATE)                   AS install_date,
    date_trunc('week', CAST(install_ts AS DATE)) AS install_week,
    channel,
    city_tier,
    device,
    low_end_device,
    language,
    CASE WHEN device = 'android' AND low_end_device THEN 'android_low_end'
         WHEN device = 'android' THEN 'android_mid_high'
         ELSE 'ios' END                         AS device_segment
FROM read_parquet('data/users.parquet');

CREATE OR REPLACE VIEW stg_events AS
SELECT
    e.event_id,
    e.user_id,
    CAST(e.event_ts AS TIMESTAMP)                                   AS event_ts,
    e.event_name,
    e.properties,
    json_extract_string(e.properties, '$.reason')                   AS kyc_fail_reason,
    TRY_CAST(json_extract(e.properties, '$.amount') AS DOUBLE)      AS amount_inr,
    json_extract_string(e.properties, '$.source')                   AS purchase_source,
    -- days since install: day 0 = install day (24h buckets from install time)
    CAST(floor(epoch(CAST(e.event_ts AS TIMESTAMP) - u.install_ts) / 86400) AS INTEGER) AS day_n
FROM read_parquet('data/events.parquet') e
JOIN stg_users u USING (user_id);
