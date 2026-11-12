CREATE OR REPLACE TABLE metric_month AS
WITH m AS (
 SELECT month,count(*) AS orders,count(DISTINCT customer_id) AS customers,sum(amount)::DECIMAL(24,6) AS amount,
 count(*) FILTER(WHERE customer_id IS NOT NULL) AS known_orders,
 sum(amount) FILTER(WHERE customer_id IS NOT NULL)::DECIMAL(24,6) AS known_amount
 FROM order_summary GROUP BY month
), enriched AS (
 SELECT *,known_orders::DOUBLE/nullif(customers,0) AS frequency,
 known_amount/nullif(known_orders,0) AS known_aov,amount/nullif(orders,0) AS aov,
 known_amount/nullif(amount,0) AS identified_amount_coverage,
 month<(SELECT complete_end_exclusive::DATE FROM settings) AS complete_month
 FROM m
)
SELECT *,CASE WHEN complete_month THEN amount/NULLIF(lag(amount) OVER(ORDER BY month),0)-1 END AS mom_rate,
 CASE WHEN complete_month THEN amount/NULLIF(lag(amount,12) OVER(ORDER BY month),0)-1 END AS yoy_rate
FROM enriched ORDER BY month;
CREATE OR REPLACE TABLE monthly_customer_type AS
SELECT month,customer_type,sum(line_amount)::DECIMAL(24,6) amount,count(DISTINCT order_key) orders,
 count(DISTINCT customer_id) customers FROM purchase_lines GROUP BY ALL;
CREATE OR REPLACE TABLE product_month AS
SELECT month,stock_code,min(Description) AS description,sum(line_amount)::DECIMAL(24,6) AS amount,
 dense_rank() OVER(PARTITION BY month ORDER BY sum(line_amount) DESC) AS amount_rank
FROM purchase_lines GROUP BY month,stock_code;
CREATE OR REPLACE TABLE cohort_cells AS
WITH sizes AS (SELECT first_month,count(*) AS cohort_size FROM customer_first GROUP BY first_month),
 active AS (SELECT first_month,date_diff('month',first_month,month) AS month_age,count(*) AS returning_customers
 FROM customer_month GROUP BY ALL),
 grid AS (SELECT s.*,r.range AS month_age, (first_month+ r.range*INTERVAL 1 MONTH)::DATE AS observation_month
 FROM sizes s CROSS JOIN range(0,25) r)
SELECT g.*,observation_month<(SELECT complete_end_exclusive::DATE FROM settings) AS complete_observation,
 CASE WHEN observation_month<(SELECT complete_end_exclusive::DATE FROM settings) THEN coalesce(a.returning_customers,0) END AS returning_customers,
 CASE WHEN observation_month<(SELECT complete_end_exclusive::DATE FROM settings) THEN coalesce(a.returning_customers,0)::DOUBLE/cohort_size END AS repurchase_rate
FROM grid g LEFT JOIN active a USING(first_month,month_age) ORDER BY first_month,month_age;
