"""Export evidence, decompose changes, check sensitivity and independently reconcile."""
from pathlib import Path
import json,itertools,math,hashlib,platform
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
import duckdb,pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1]

def run(db=None,output=None):
 cfg=json.loads((ROOT/'config/analysis.json').read_text()); out=Path(output or ROOT)
 V=out/'validation'; E=out/'data/exports'; V.mkdir(parents=True,exist_ok=True);E.mkdir(parents=True,exist_ok=True)
 c=duckdb.connect(str(db or ROOT/'data/processed/retail.duckdb'))
 c.execute((ROOT/'sql/04_contributions.sql').read_text())
 checks=[]
 def check(name,ok,detail):
  checks.append({'check':name,'passed':bool(ok),'detail':str(detail)})
 def export(name,query,folder=V):
  df=c.execute(query).fetchdf();df.to_csv(folder/f'{name}.csv',index=False);return df
 def scalar(q): return c.execute(q).fetchone()[0]
 for table in ['metric_month','monthly_customer_type','product_month','cohort_cells','quality_summary','quality_month','group_contributions']:
  order={'monthly_customer_type':' ORDER BY month,customer_type','product_month':' ORDER BY month,amount_rank,stock_code'}.get(table,'')
  export(table,'SELECT * FROM '+table+order,E)
 for table in ['invoice_audit','daily_coverage','cancellation_candidates']:
  export(table,'SELECT * FROM '+table)
 export('flag_intersections', '''SELECT cross_sheet_duplicate,is_cancelled,sign(qty) quantity_sign,sign(unit_price) price_sign,
 non_merchandise,customer_id IS NULL missing_customer,count(*) rows,sum(line_amount) signed_amount FROM clean_lines GROUP BY ALL ORDER BY ALL''')
 export('non_merchandise_codes', '''SELECT stock_code,min(Description) description,count(*) rows,count(DISTINCT order_key) orders,sum(line_amount) signed_amount,
 sum(line_amount) FILTER(WHERE qty>0 AND unit_price>0 AND NOT is_cancelled) positive_amount
 FROM clean_lines WHERE NOT cross_sheet_duplicate AND non_merchandise GROUP BY stock_code ORDER BY rows DESC''')
 export('description_changes', '''SELECT stock_code,count(DISTINCT Description) descriptions,min(Description) first_example,max(Description) last_example
 FROM clean_lines WHERE NOT cross_sheet_duplicate GROUP BY stock_code HAVING descriptions>1 ORDER BY descriptions DESC''')
 export('quality_samples', '''SELECT * FROM clean_lines QUALIFY row_number() OVER(PARTITION BY record_type ORDER BY line_id)<=5''')
 export('anomaly_samples', '''SELECT issue,line_id,Invoice,StockCode,Description,Quantity,Price,"Customer ID",invoice_ts,line_amount,record_type FROM clean_lines CROSS JOIN LATERAL (SELECT 'missing_customer' issue WHERE customer_id IS NULL UNION ALL SELECT 'negative_price' WHERE unit_price<0 UNION ALL SELECT 'zero_price' WHERE unit_price=0 UNION ALL SELECT 'negative_quantity' WHERE qty<0 UNION ALL SELECT 'cancelled_positive' WHERE is_cancelled AND qty>0 UNION ALL SELECT 'within_sheet_duplicate' WHERE within_sheet_occurrence>1) f WHERE NOT cross_sheet_duplicate QUALIFY row_number() OVER(PARTITION BY issue ORDER BY line_id)<=3''')
 export('duplicate_samples', '''SELECT line_id,signature,Invoice,StockCode,Description,Quantity,InvoiceDate,Price,"Customer ID",Country,cross_sheet_duplicate,within_sheet_occurrence
 FROM clean_lines WHERE cross_sheet_duplicate OR within_sheet_occurrence>1 ORDER BY signature,source_sheet,source_row LIMIT 100''')
 export('same_sheet_duplicate_summary', '''SELECT count(*) extra_rows,sum(line_amount) signed_amount,
 sum(line_amount) FILTER(WHERE is_valid_purchase) positive_amount FROM clean_lines WHERE NOT cross_sheet_duplicate AND within_sheet_occurrence>1''')
 export('cancel_match_summary', '''SELECT CASE WHEN customer_id IS NULL THEN 'unknown_customer' WHEN candidate_lines=0 THEN 'no_candidate'
 WHEN candidate_lines=1 THEN 'one_candidate_line' ELSE 'multiple_candidate_lines' END category,count(*) rows,sum(abs(line_amount)) absolute_amount
 FROM cancellation_candidates GROUP BY category ORDER BY category''')
 export('text_audit', '''SELECT count(*) FILTER(WHERE Invoice!=trim(Invoice)) invoice_whitespace,
 count(*) FILTER(WHERE StockCode!=trim(StockCode)) stock_whitespace,count(*) FILTER(WHERE "Customer ID"!=trim("Customer ID")) customer_whitespace,
 count(*) FILTER(WHERE Country!=trim(Country)) country_whitespace,count(*) FILTER(WHERE Description!=trim(Description)) description_whitespace,
 count(*) FILTER(WHERE "Customer ID" IS NOT NULL AND NOT regexp_full_match("Customer ID",'[0-9]+')) non_integer_customer_ids,
 count(*) FILTER(WHERE Description IS NULL) missing_description FROM raw_lines''')
 export('amount_precision', '''SELECT max(abs(CAST(Price AS DOUBLE)-CAST(unit_price AS DOUBLE))) max_double_difference,
 count(*) FILTER(WHERE unit_price*100!=round(unit_price*100)) non_cent_prices FROM clean_lines''')
 export('cross_sheet_evidence', '''WITH g AS (SELECT signature,source_sheet,count(*) n FROM clean_lines GROUP BY ALL)
 SELECT count(*) signatures,sum(least(a.n,b.n)) duplicate_copies,sum(abs(a.n-b.n)) multiplicity_difference
 FROM g a JOIN g b ON a.signature=b.signature AND a.source_sheet<b.source_sheet''')
 export('order_time_variation','SELECT * FROM invoice_audit WHERE timestamps>1 ORDER BY invoice_no')
 export('monthly_signed_bridge', '''SELECT month,sum(line_amount) raw_signed_amount,
 sum(line_amount) FILTER(WHERE cross_sheet_duplicate) removed_overlap_signed,
 sum(line_amount) FILTER(WHERE NOT cross_sheet_duplicate) canonical_signed_amount,
 sum(line_amount) FILTER(WHERE in_signed_merchandise_records) signed_merchandise_records
 FROM clean_lines GROUP BY month ORDER BY month''')
 export('top_orders','SELECT * FROM order_summary ORDER BY amount DESC LIMIT 30')
 export('cohort_customer_examples', '''SELECT cm.* FROM customer_month cm JOIN
 (SELECT customer_id FROM customer_first WHERE first_month IN (DATE '2009-12-01',DATE '2010-11-01',DATE '2011-10-01')
 QUALIFY row_number() OVER(PARTITION BY first_month ORDER BY customer_id)<=3) s USING(customer_id) ORDER BY customer_id,month''')
 export('frequency_segments', '''WITH customers AS (SELECT customer_id,count(*) orders,sum(amount) amount FROM order_summary
 WHERE customer_id IS NOT NULL AND month<(SELECT complete_end_exclusive::DATE FROM settings) GROUP BY customer_id)
 SELECT CASE WHEN orders=1 THEN '1 order' WHEN orders<=3 THEN '2-3 orders' WHEN orders<=9 THEN '4-9 orders' ELSE '10+ orders' END segment,
 count(*) customers,sum(orders) orders,sum(amount) amount FROM customers GROUP BY segment ORDER BY segment''',E)
 export('cohort_comparison', '''SELECT year(first_month) cohort_year,sum(cohort_size) cohort_customers,sum(returning_customers) returning_customers,
 sum(returning_customers)::DOUBLE/sum(cohort_size) month1_rate FROM cohort_cells WHERE month_age=1 AND complete_observation
 AND month(first_month) BETWEEN 1 AND 10 AND year(first_month) IN(2010,2011) GROUP BY cohort_year ORDER BY cohort_year''',E)
 # Exact integer-micro-unit aggregation by pandas, independently of SQL's order_summary.
 p=c.execute('''SELECT order_key,customer_id,month,stock_code,country_name,(line_amount*1000000)::BIGINT amount_micro
 FROM clean_lines WHERE is_valid_purchase''').fetchdf()
 py=p.groupby('month').agg(amount_micro=('amount_micro','sum'),orders=('order_key','nunique'),customers=('customer_id','nunique'))
 known=p[p.customer_id.notna()].groupby('month').agg(known_micro=('amount_micro','sum'),known_orders=('order_key','nunique'))
 py=py.join(known)
 sq=c.execute('''SELECT month,(amount*1000000)::BIGINT amount_micro,orders,customers,(known_amount*1000000)::BIGINT known_micro,known_orders,
 frequency,known_aov,aov FROM metric_month''').fetchdf().set_index('month')
 differences=py-sq[py.columns];differences.to_csv(V/'independent_monthly_differences.csv')
 check('independent_monthly_amount_counts',(differences==0).all().all(),f'{len(py)} months; exact micro-GBP, orders, customers, known scope')
 for col,expected in [('frequency',py.known_orders/py.customers),('known_aov',py.known_micro/1e6/py.known_orders),('aov',py.amount_micro/1e6/py.orders)]:
  err=float(abs(expected-sq[col]).max());check('independent_'+col,err<=1e-8,err)
 # Recompute every line amount from raw text with Decimal, not from SQL result.
 raw=c.execute('SELECT Quantity,Price,(line_amount*1000000)::BIGINT micro FROM clean_lines').fetchall()
 err=max(abs(int((Decimal(q)*Decimal(price)).quantize(Decimal('0.000001'))*1000000)-micro) for q,price,micro in raw)
 check('raw_decimal_line_amounts',err==0,f'{len(raw)} rows; max micro-GBP difference {err}')
 del raw
 # Meaningful full-dataset invariants.
 queries={
 'overlap_multiset_exact':"SELECT count(*)=0 FROM ((SELECT Invoice,StockCode,Description,Quantity,InvoiceDate,Price,\"Customer ID\",Country FROM clean_lines WHERE source_sheet='Year 2009-2010' AND invoice_ts>='2010-12-01' AND invoice_ts<'2010-12-10' EXCEPT ALL SELECT Invoice,StockCode,Description,Quantity,InvoiceDate,Price,\"Customer ID\",Country FROM clean_lines WHERE source_sheet='Year 2010-2011' AND invoice_ts>='2010-12-01' AND invoice_ts<'2010-12-10') UNION ALL (SELECT Invoice,StockCode,Description,Quantity,InvoiceDate,Price,\"Customer ID\",Country FROM clean_lines WHERE source_sheet='Year 2010-2011' AND invoice_ts>='2010-12-01' AND invoice_ts<'2010-12-10' EXCEPT ALL SELECT Invoice,StockCode,Description,Quantity,InvoiceDate,Price,\"Customer ID\",Country FROM clean_lines WHERE source_sheet='Year 2009-2010' AND invoice_ts>='2010-12-01' AND invoice_ts<'2010-12-10'))",
 'raw_row_conservation':"SELECT (SELECT count(*) FROM raw_lines)=(SELECT count(*) FROM clean_lines)",
 'unique_source_line':"SELECT count(*)=count(DISTINCT line_id) FROM clean_lines",
 'unique_order_key':"SELECT count(*)=count(DISTINCT order_key) FROM order_summary",
 'invoice_no_customer_country_date_conflict':"SELECT count(*)=0 FROM invoice_audit WHERE customers>1 OR countries>1 OR dates>1 OR (missing_customer_rows>0 AND missing_customer_rows<rows)",
 'order_amount_reconciliation':"SELECT (SELECT sum(line_amount) FROM clean_lines WHERE is_valid_purchase)=(SELECT sum(amount) FROM order_summary)",
 'join_no_fanout':"SELECT (SELECT count(*) FROM purchase_lines)=(SELECT count(*) FROM clean_lines WHERE is_valid_purchase)",
 'join_amount_unchanged':"SELECT (SELECT sum(line_amount) FROM purchase_lines)=(SELECT sum(amount) FROM order_summary)",
 'customer_month_amount':"SELECT (SELECT sum(amount) FROM customer_month)=(SELECT sum(amount) FROM order_summary WHERE customer_id IS NOT NULL)",
 'cohort_unique_cells':"SELECT count(*)=count(DISTINCT (first_month,month_age)) FROM cohort_cells",
 'cohort_numerator_bounds':"SELECT count(*)=0 FROM cohort_cells WHERE returning_customers<0 OR returning_customers>cohort_size",
 'cohort_incomplete_null':"SELECT count(*)=0 FROM cohort_cells WHERE NOT complete_observation AND (returning_customers IS NOT NULL OR repurchase_rate IS NOT NULL)",
 'cohort_complete_nonnull':"SELECT count(*)=0 FROM cohort_cells WHERE complete_observation AND (returning_customers IS NULL OR repurchase_rate IS NULL)",
 'cohort_month0_identity':"SELECT count(*)=0 FROM cohort_cells WHERE month_age=0 AND complete_observation AND returning_customers!=cohort_size",
 'no_invalid_required_rows':"SELECT count(*)=0 FROM clean_lines WHERE record_type='invalid_required_field'",
 'overlap_only_expected_dates':"SELECT count(*)=0 FROM clean_lines WHERE cross_sheet_duplicate AND (invoice_ts<'2010-12-01' OR invoice_ts>='2010-12-10')",
 }
 for name,q in queries.items(): check(name,scalar(q),q)
 reconciliation=export('sql_reconciliation',(ROOT/'sql/05_reconcile.sql').read_text())
 check('standalone_sql_reconciliation',(reconciliation.expected==reconciliation.actual).all(),f'{len(reconciliation)} SQL controls; exact agreement')
 # Independently derive full-history first observation and all observed cohort cells from distinct customer-months.
 cm=p[p.customer_id.notna()][['customer_id','month']].drop_duplicates()
 first=cm.groupby('customer_id').month.min().rename('first_month');cm=cm.join(first,on='customer_id')
 cm['age']=(cm.month.dt.year-cm.first_month.dt.year)*12+cm.month.dt.month-cm.first_month.dt.month
 active=cm.groupby(['first_month','age']).size();sizes=first.value_counts()
 cohort=c.execute('SELECT * FROM cohort_cells').fetchdf();cerr=[]
 for r in cohort.itertuples():
  if r.complete_observation:
   cerr.append(int(r.returning_customers)-int(active.get((r.first_month,r.month_age),0)))
  assert r.cohort_size==sizes[r.first_month]
 check('independent_cohort_counts',all(x==0 for x in cerr),f'{len(cerr)} complete cells; independently reconstructed customer first month')
 # Three scope samples useful for later dashboard verification (no dashboard tested here).
 scopes=[('UK_2011_11','2011-11-01','2011-12-01','United Kingdom'),('Germany_2011_09_11','2011-09-01','2011-12-01','Germany'),('All_2011_Q3','2011-07-01','2011-10-01',None)]
 scope_rows=[]
 for name,start,end,country in scopes:
  z=p[(p.month>=start)&(p.month<end)]
  condition='month>=? AND month<?';params=[start,end]
  if country: z=z[z.country_name==country];condition+=' AND country_name=?';params.append(country)
  sql=c.execute(f'SELECT coalesce(sum(line_amount),0),count(DISTINCT order_key),count(DISTINCT customer_id) FROM purchase_lines WHERE {condition}',params).fetchone()
  vals=[int(z.amount_micro.sum())/1e6,z.order_key.nunique(),z.customer_id.nunique()]
  ok=abs(vals[0]-float(sql[0]))<1e-8 and vals[1:]==list(sql[1:]);check('scope_'+name,ok,vals)
  scope_rows.append(dict(scope=name,start=start,end_exclusive=end,country=country or 'All',amount=vals[0],orders=vals[1],customers=vals[2],aov=vals[0]/vals[1]))
 pd.DataFrame(scope_rows).to_csv(V/'scope_checks.csv',index=False)
 # Multi-product order demonstrates COUNTD vs summed product counts.
 multi=export('multi_product_example', '''SELECT order_key,count(DISTINCT stock_code) products,count(DISTINCT order_key) actual_orders
 FROM purchase_lines GROUP BY order_key HAVING products>1 ORDER BY order_key LIMIT 1''')
 check('multi_product_dedup',int(multi.iloc[0].actual_orders)==1 and int(multi.iloc[0].products)>1,multi.to_dict('records'))
 # Full-scope yearly comparison factors.
 metrics=c.execute('SELECT * FROM metric_month ORDER BY month').fetchdf();metrics['month']=metrics.month.dt.strftime('%Y-%m-%d')
 base=metrics[metrics.month==cfg['base_month']].iloc[0];cur=metrics[metrics.month==cfg['current_month']].iloc[0]
 x=[float(base.customers),float(base.frequency),float(base.known_aov)];y=[float(cur.customers),float(cur.frequency),float(cur.known_aov)]
 from analysis_utils import shapley
 contributions=shapley(x,y)
 factors=pd.DataFrame({'factor':['customers','frequency','aov'],'base_value':x,'current_value':y,'contribution':contributions})
 factors.to_csv(E/'factor_contributions.csv',index=False)
 delta=float(cur.known_amount-base.known_amount)
 check('shapley_closure',abs(sum(contributions)-delta)<=.01,{'residual':sum(contributions)-delta})
 check('factor_identity',max(abs(math.prod(x)-base.known_amount),abs(math.prod(y)-cur.known_amount))<=.01,'Both periods')
 groups=c.execute('SELECT * FROM group_contributions').fetchdf()
 for dimension,df in groups.groupby('dimension'):
  check('group_closure_'+dimension,abs(df.contribution.sum()-(cur.amount-base.amount))<=.01,df.contribution.sum())
 # Predeclare global complete-period 99th-percentile order threshold; keep main population intact.
 threshold=float(c.execute('SELECT quantile_cont(amount,?) FROM order_summary WHERE month<?',[cfg['extreme_order_quantile'],cfg['complete_end_exclusive']]).fetchone()[0])
 scenarios={
 'primary':'is_valid_purchase',
 'dedup_within_sheet':'is_valid_purchase AND within_sheet_occurrence=1',
 'exclude_top1pct_orders':f'is_valid_purchase AND order_key IN (SELECT order_key FROM order_summary WHERE amount<={threshold})',
 'dedup_and_trim':f'is_valid_purchase AND within_sheet_occurrence=1 AND order_key IN (SELECT order_key FROM order_summary WHERE amount<={threshold})',
 'include_nonmerchandise_positive':'NOT cross_sheet_duplicate AND NOT is_cancelled AND qty>0 AND unit_price>0',
 'without_overlap_dedup':'NOT non_merchandise AND NOT is_cancelled AND qty>0 AND unit_price>0'
 }
 sens=[];ranks=[]
 for name,cond in scenarios.items():
  d=c.execute(f'''SELECT month,sum(line_amount) amount,sum(line_amount) FILTER(WHERE customer_id IS NOT NULL) known_amount,
  count(DISTINCT customer_id) customers,count(DISTINCT order_key) orders FROM clean_lines WHERE {cond}
  AND month IN(?,?) GROUP BY month ORDER BY month''',[cfg['base_month'],cfg['current_month']]).fetchdf()
  b,n=d.iloc[0],d.iloc[1];sens.append(dict(scenario=name,base_amount=b.amount,current_amount=n.amount,change=n.amount-b.amount,growth=n.amount/b.amount-1,known_change=n.known_amount-b.known_amount,known_growth=n.known_amount/b.known_amount-1,threshold=threshold))
  rank=c.execute(f'''SELECT stock_code,sum(CASE WHEN month=? THEN line_amount ELSE -line_amount END) contribution
   FROM clean_lines WHERE {cond} AND month IN (?,?) GROUP BY stock_code ORDER BY abs(contribution) DESC,stock_code LIMIT 10''',[cfg['current_month'],cfg['base_month'],cfg['current_month']]).fetchdf()
  rank['scenario']=name;rank['rank']=range(1,len(rank)+1);ranks.append(rank)
 pd.DataFrame(sens).to_csv(E/'sensitivity.csv',index=False);pd.concat(ranks).to_csv(V/'sensitivity_product_ranks.csv',index=False)
 # Independent boundary checks in separate, explicitly simulated data only.
 from analysis_utils import safe_ratio,cohort_rate,shapley
 check('synthetic_zero_denominator',safe_ratio(10,0) is None,'Synthetic utility check, not business data')
 check('synthetic_zero_repurchase',cohort_rate(0,5,True)==0 and cohort_rate(0,5,False) is None,'Zero != unobserved')
 check('synthetic_shapley',abs(sum(shapley([2,3,4],[3,4,5]))-36)<1e-8,'Synthetic 24 -> 60; mixed interactions')
 # Export analysis-ready files; typed parquet remains in database; CSV types documented separately.
 export('period_contribution', "SELECT '2011-11_vs_2010-11' comparison_id,* FROM group_contributions",E)
 c.execute("COPY (SELECT line_id AS LineID,order_key AS OrderKey,customer_id AS CustomerID,invoice_ts AS InvoiceDate,month AS Month,stock_code AS StockCode,Description,country_name AS Country,qty AS Quantity,unit_price AS UnitPrice,line_amount AS LineAmount,is_valid_purchase AS IsValidPurchase,first_month AS FirstObservedMonth,customer_type AS CustomerType FROM purchase_lines ORDER BY line_id) TO ? (HEADER, DELIMITER ',')",[str(E/'sales_lines.csv')])
 overview=c.execute('''SELECT count(*) lines,count(DISTINCT order_key) orders,count(DISTINCT customer_id) customers,sum(line_amount) amount,
 sum(line_amount) FILTER(WHERE customer_id IS NOT NULL) known_amount FROM purchase_lines WHERE month<?''',[cfg['complete_end_exclusive']]).fetchdf().to_dict('records')[0]
 summary={'config':cfg,'overview_complete_period':overview,'base':base.to_dict(),'current':cur.to_dict(),'factor_contributions':factors.to_dict('records'),
 'extreme_order_threshold':threshold,'sensitivity':sens,'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),
 'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'runtime':{'python':platform.python_version(),'duckdb':duckdb.__version__,'pandas':pd.__version__,'numpy':np.__version__}}
 def conv(v):
  if isinstance(v,np.generic):return v.item()
  if isinstance(v,(pd.Timestamp,datetime)):return str(v)
  if isinstance(v,Decimal):return float(v)
  raise TypeError(type(v))
 (E/'analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=conv)+'\n')
 pd.DataFrame(checks).to_csv(V/'checks.csv',index=False)
 c.close()
 failed=[x for x in checks if not x['passed']];print(json.dumps({'passed':len(checks)-len(failed),'total':len(checks),'failures':failed,'threshold':threshold,'sensitivity':sens},default=conv,indent=2),flush=True)
 assert not failed,failed
if __name__=='__main__':run()
