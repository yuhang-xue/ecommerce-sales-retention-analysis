from pathlib import Path
import duckdb,json
R=Path(__file__).resolve().parents[1]
c=duckdb.connect(str(R/'data/processed/retail.duckdb'))
c.execute('CREATE OR REPLACE TABLE raw_lines AS SELECT * FROM read_csv(?,all_varchar=true)',[str(R/'data/processed/raw_lines.csv')])
c.execute('''CREATE OR REPLACE VIEW profile_lines AS SELECT *, CAST(Quantity AS BIGINT) q,CAST(Price AS DECIMAL(20,6)) p,
 make_timestamp(CAST(round((CAST(InvoiceDate AS DOUBLE)-25569)*86400) AS BIGINT)*1000000) dt,
 md5(to_json(struct_pack(i:=Invoice,s:=StockCode,d:=Description,q:=Quantity,t:=InvoiceDate,p:=Price,c:="Customer ID",n:=Country))) sig
 FROM raw_lines''')
queries={
'cross_sheet':'''WITH g AS (SELECT sig, count(*) n,count(DISTINCT source_sheet) sheets FROM profile_lines GROUP BY sig) SELECT sheets,count(*) signatures,sum(n) rows FROM g GROUP BY sheets''',
'cross_sheet_counts':'''WITH g AS (SELECT sig,source_sheet,count(*) n FROM profile_lines GROUP BY ALL) SELECT count(*) signatures,sum(least(a.n,b.n)) overlapping_copies,sum(abs(a.n-b.n)) multiplicity_difference FROM g a JOIN g b ON a.sig=b.sig AND a.source_sheet<b.source_sheet''',
'invoice_conflicts':'''SELECT Invoice,count(DISTINCT "Customer ID") customers,count(DISTINCT Country) countries,count(DISTINCT dt::DATE) dates,min(dt) first_date,max(dt) last_date,count(*) lines FROM profile_lines GROUP BY Invoice HAVING customers>1 OR countries>1 OR dates>1 ORDER BY lines DESC LIMIT 25''',
'codes':'''SELECT StockCode,min(Description) description,count(*) n,sum(q*p) amount FROM profile_lines WHERE NOT regexp_full_match(StockCode,'[0-9]{5}[A-Za-z]*') GROUP BY StockCode ORDER BY n DESC LIMIT 50''',
'signs':'''SELECT starts_with(upper(Invoice),'C') cancelled,sign(q) quantity_sign,sign(p) price_sign,count(*) n,sum(q*p) amount FROM profile_lines GROUP BY ALL ORDER BY ALL''',
'precision':'''SELECT max(length(split_part(Price,'.',2))) max_decimals, count(*) FILTER (WHERE try_cast(Price AS DECIMAL(20,6)) IS NULL) invalid_price FROM raw_lines''',
'overlap_dates':'''SELECT source_sheet,dt::DATE date,count(*) n FROM profile_lines WHERE dt>='2010-12-01' AND dt<'2010-12-10' GROUP BY ALL ORDER BY date,source_sheet'''}
for name,q in queries.items():
 d=c.execute(q).fetchdf(); d.to_csv(R/f'validation/initial_{name}.csv',index=False); print(name,d.to_string(index=False),flush=True)
c.close()
