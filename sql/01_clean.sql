-- raw_lines retains the original eight XML values as strings.
CREATE OR REPLACE TABLE standard_lines AS
WITH typed AS (
 SELECT *, source_sheet || ':' || source_row AS line_id,
   NULLIF(trim(Invoice),'') AS invoice_no, NULLIF(trim(StockCode),'') AS stock_code,
   NULLIF(trim("Customer ID"),'') AS customer_id, NULLIF(trim(Country),'') AS country_name,
   try_cast(Quantity AS BIGINT) AS qty, try_cast(Price AS DECIMAL(18,6)) AS unit_price,
   make_timestamp(CAST(round((try_cast(InvoiceDate AS DOUBLE)-25569)*86400) AS BIGINT)*1000000) AS invoice_ts,
   md5(to_json(struct_pack(i:=Invoice,s:=StockCode,d:=Description,q:=Quantity,t:=InvoiceDate,p:=Price,c:="Customer ID",n:=Country))) AS signature
 FROM raw_lines
), flags AS (
 SELECT *, (qty*unit_price)::DECIMAL(24,6) AS line_amount,
   date_trunc('month',invoice_ts)::DATE AS month,
   starts_with(upper(invoice_no),'C') AS is_cancelled,
   max(source_sheet) OVER (PARTITION BY signature) > source_sheet AS cross_sheet_duplicate,
   row_number() OVER (PARTITION BY source_sheet,signature ORDER BY CAST(source_row AS BIGINT)) AS within_sheet_occurrence,
   upper(stock_code) IN (SELECT code FROM excluded_codes) OR starts_with(upper(stock_code),'GIFT_') AS non_merchandise
 FROM typed
)
SELECT *, CASE
 WHEN cross_sheet_duplicate THEN 'cross_sheet_duplicate'
 WHEN invoice_no IS NULL OR stock_code IS NULL OR qty IS NULL OR unit_price IS NULL OR invoice_ts IS NULL THEN 'invalid_required_field'
 WHEN non_merchandise THEN 'non_merchandise'
 WHEN unit_price<=0 THEN 'nonpositive_price'
 WHEN is_cancelled AND qty>=0 THEN 'cancelled_nonnegative'
 WHEN is_cancelled AND qty<0 THEN 'cancellation'
 WHEN qty<0 THEN 'negative_adjustment'
 WHEN qty=0 THEN 'zero_quantity'
 ELSE 'positive_purchase' END AS record_type
FROM flags;
CREATE OR REPLACE TABLE clean_lines AS
SELECT *, invoice_no AS order_key, record_type='positive_purchase' AS is_valid_purchase,
 record_type IN ('positive_purchase','cancellation','negative_adjustment') AS in_signed_merchandise_records
FROM standard_lines;
CREATE OR REPLACE TABLE order_summary AS
SELECT order_key, min(invoice_ts) AS order_ts, min(month) AS month,
 min(customer_id) AS customer_id,min(country_name) AS country,
 count(*) AS line_count,count(DISTINCT stock_code) AS product_count,
 sum(line_amount)::DECIMAL(24,6) AS amount
FROM clean_lines WHERE is_valid_purchase GROUP BY order_key;
CREATE OR REPLACE TABLE customer_first AS
SELECT customer_id,min(month) AS first_month FROM order_summary WHERE customer_id IS NOT NULL GROUP BY customer_id;
CREATE OR REPLACE TABLE customer_month AS
SELECT o.customer_id,o.month,f.first_month,count(*) AS orders,sum(o.amount)::DECIMAL(24,6) AS amount
FROM order_summary o JOIN customer_first f USING(customer_id) GROUP BY ALL;
CREATE OR REPLACE VIEW purchase_lines AS
SELECT l.*,f.first_month,CASE WHEN l.customer_id IS NULL THEN 'Unknown'
 WHEN l.month=f.first_month THEN 'New' ELSE 'Existing' END AS customer_type
FROM clean_lines l LEFT JOIN customer_first f USING(customer_id) WHERE l.is_valid_purchase;
