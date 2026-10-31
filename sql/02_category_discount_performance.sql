SELECT
    category,
    COUNT(DISTINCT transaction_id) AS transactions,
    SUM(quantity) AS units_sold,
    ROUND(SUM(gross_amount), 2) AS gross_sales,
    ROUND(SUM(discount_amount), 2) AS discount_total,
    ROUND(SUM(net_amount), 2) AS net_sales,
    ROUND(
        CASE
            WHEN SUM(gross_amount) > 0
            THEN (SUM(discount_amount) * 100.0) / SUM(gross_amount)
            ELSE 0.0
        END,
        2
    ) AS effective_discount_rate_pct
FROM curated_transactions
GROUP BY category
ORDER BY net_sales DESC;
