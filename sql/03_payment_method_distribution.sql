SELECT
    payment_method,
    currency,
    COUNT(DISTINCT transaction_id) AS transaction_count,
    ROUND(SUM(net_amount), 2) AS total_net_volume,
    ROUND(AVG(net_amount), 2) AS avg_ticket_size,
    ROUND(
        (COUNT(DISTINCT transaction_id) * 100.0) / (
            SELECT COUNT(DISTINCT transaction_id)
            FROM curated_transactions
        ),
        2
    ) AS transaction_share_pct
FROM curated_transactions
GROUP BY
    payment_method,
    currency
ORDER BY total_net_volume DESC;
