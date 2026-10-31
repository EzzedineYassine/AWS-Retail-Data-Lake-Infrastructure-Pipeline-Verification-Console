SELECT
    SUBSTR(transaction_timestamp, 12, 2) AS hour_of_day_utc,
    COUNT(DISTINCT transaction_id) AS transaction_count,
    COUNT(DISTINCT customer_id) AS distinct_customers,
    SUM(quantity) AS total_items,
    ROUND(SUM(net_amount), 2) AS hourly_net_revenue
FROM curated_transactions
GROUP BY SUBSTR(transaction_timestamp, 12, 2)
ORDER BY hour_of_day_utc ASC;
