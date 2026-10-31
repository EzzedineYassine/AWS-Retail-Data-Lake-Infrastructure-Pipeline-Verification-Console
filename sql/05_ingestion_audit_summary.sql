SELECT
    source_file,
    transaction_date,
    MIN(ingested_at_utc) AS first_ingested_at_utc,
    MAX(ingested_at_utc) AS last_ingested_at_utc,
    COUNT(*) AS curated_row_count,
    ROUND(SUM(net_amount), 2) AS partition_net_revenue
FROM curated_transactions
GROUP BY
    source_file,
    transaction_date
ORDER BY
    source_file ASC,
    transaction_date ASC;
