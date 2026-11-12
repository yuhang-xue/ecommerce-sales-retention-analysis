CREATE OR REPLACE TABLE quality_summary AS
SELECT record_type,count(*) AS rows,count(DISTINCT order_key) AS invoices,
 sum(line_amount)::DECIMAL(24,6) AS signed_amount,sum(abs(line_amount))::DECIMAL(24,6) AS absolute_amount
FROM clean_lines GROUP BY record_type ORDER BY rows DESC;
CREATE OR REPLACE TABLE quality_month AS
SELECT month,count(*) raw_rows,count(*) FILTER(WHERE cross_sheet_duplicate) cross_sheet_duplicates,
 count(*) FILTER(WHERE NOT cross_sheet_duplicate) canonical_rows,
 count(*) FILTER(WHERE NOT cross_sheet_duplicate AND customer_id IS NULL) missing_customer_rows,
 count(*) FILTER(WHERE is_valid_purchase) positive_rows,
 count(*) FILTER(WHERE is_valid_purchase AND customer_id IS NOT NULL) known_positive_rows,
 sum(line_amount) FILTER(WHERE is_valid_purchase) positive_amount,
 sum(line_amount) FILTER(WHERE is_valid_purchase AND customer_id IS NULL) unknown_positive_amount,
 sum(line_amount) FILTER(WHERE in_signed_merchandise_records) signed_merchandise_amount
FROM clean_lines GROUP BY month ORDER BY month;
CREATE OR REPLACE TABLE invoice_audit AS
SELECT invoice_no,count(DISTINCT customer_id) AS customers,count(DISTINCT country_name) AS countries,
 count(DISTINCT invoice_ts::DATE) AS dates,count(DISTINCT invoice_ts) AS timestamps,
 count(*) FILTER(WHERE customer_id IS NULL) missing_customer_rows,count(*) AS rows
FROM clean_lines WHERE NOT cross_sheet_duplicate GROUP BY invoice_no;
CREATE OR REPLACE TABLE daily_coverage AS
WITH calendar AS (SELECT range::DATE AS date FROM range(TIMESTAMP '2009-12-01',TIMESTAMP '2011-12-10',INTERVAL 1 DAY)),
 counts AS (SELECT invoice_ts::DATE AS date,count(*) canonical_rows,count(*) FILTER(WHERE is_valid_purchase) positive_rows
 FROM clean_lines WHERE NOT cross_sheet_duplicate GROUP BY date)
SELECT date,dayname(date) AS weekday,coalesce(canonical_rows,0) canonical_rows,coalesce(positive_rows,0) positive_rows
FROM calendar LEFT JOIN counts USING(date) ORDER BY date;
-- Exact candidate lookup is only a heuristic. It does not allocate a purchase to one cancellation.
CREATE OR REPLACE TABLE cancellation_candidates AS
SELECT c.line_id,c.invoice_no,c.customer_id,c.stock_code,c.invoice_ts,c.line_amount,
 count(p.line_id) AS candidate_lines,count(DISTINCT p.order_key) AS candidate_orders,
 min(p.invoice_ts) AS earliest_candidate,max(p.invoice_ts) AS latest_candidate
FROM clean_lines c LEFT JOIN purchase_lines p ON c.customer_id=p.customer_id AND c.stock_code=p.stock_code
 AND -c.qty=p.qty AND c.unit_price=p.unit_price AND p.invoice_ts<c.invoice_ts
WHERE c.record_type='cancellation' GROUP BY ALL;
