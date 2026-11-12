CREATE OR REPLACE TABLE group_contributions AS
WITH scoped AS (
 SELECT *,month=(SELECT current_month::DATE FROM settings) AS current_period
 FROM purchase_lines WHERE month IN ((SELECT base_month::DATE FROM settings),(SELECT current_month::DATE FROM settings))
), unpivoted AS (
 SELECT 'product' dimension,stock_code AS group_name,current_period,line_amount FROM scoped
 UNION ALL SELECT 'country',country_name,current_period,line_amount FROM scoped
 UNION ALL SELECT 'customer_type',customer_type,current_period,line_amount FROM scoped
), grouped AS (
 SELECT dimension,group_name,coalesce(sum(line_amount) FILTER(WHERE NOT current_period),0)::DECIMAL(24,6) base_amount,
 coalesce(sum(line_amount) FILTER(WHERE current_period),0)::DECIMAL(24,6) current_amount
 FROM unpivoted GROUP BY dimension,group_name
)
SELECT *,current_amount-base_amount AS contribution,
 dense_rank() OVER(PARTITION BY dimension ORDER BY abs(current_amount-base_amount) DESC) AS absolute_contribution_rank
FROM grouped ORDER BY dimension,absolute_contribution_rank,group_name;
