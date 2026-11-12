-- Read-only controls; each result is an independently stated balance or key check.
SELECT 'raw_to_clean_rows' AS control,
 (SELECT count(*) FROM raw_lines)::DECIMAL(30,6) AS expected,
 (SELECT count(*) FROM clean_lines)::DECIMAL(30,6) AS actual
UNION ALL
SELECT 'purchase_lines_to_orders_amount',
 (SELECT sum(line_amount) FROM clean_lines WHERE is_valid_purchase),
 (SELECT sum(amount) FROM order_summary)
UNION ALL
SELECT 'orders_to_month_amount',(SELECT sum(amount) FROM order_summary),(SELECT sum(amount) FROM metric_month)
UNION ALL
SELECT 'known_orders_to_customer_month_amount',
 (SELECT sum(amount) FROM order_summary WHERE customer_id IS NOT NULL),(SELECT sum(amount) FROM customer_month)
UNION ALL
SELECT 'quality_class_rows',(SELECT count(*) FROM raw_lines),(SELECT sum(rows) FROM quality_summary)
UNION ALL
SELECT 'order_key_uniqueness',(SELECT count(DISTINCT order_key) FROM order_summary),(SELECT count(*) FROM order_summary)
UNION ALL
SELECT 'cohort_key_uniqueness',(SELECT count(DISTINCT(first_month,month_age)) FROM cohort_cells),(SELECT count(*) FROM cohort_cells);
