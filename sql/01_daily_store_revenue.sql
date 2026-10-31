SELECT
    transaction_date,
    store_id,
    currency,
    COUNT(DISTINCT transaction_id) AS transaction_count,
    SUM(quantity) AS total_units_sold,
    ROUND(SUM(gross_amount), 2) AS gross_revenue,
    ROUND(SUM(discount_amount), 2) AS total_discounts,
    ROUND(SUM(net_amount), 2) AS net_revenue,
    ROUND(AVG(net_amount), 2) AS avg_transaction_value
FROM curated_transactions
GROUP BY
    transaction_date,
    store_id,
    currency
ORDER BY
    transaction_date ASC,
    net_revenue DESC;
