from pathlib import Path
import json,duckdb,argparse
from extract_raw import extract
ROOT=Path(__file__).resolve().parents[1]
def build(out=None,reextract=False):
 out=Path(out or ROOT/'data/processed');out.mkdir(parents=True,exist_ok=True)
 csv=out/'raw_lines.csv'
 if reextract or not csv.exists(): extract(csv)
 cfg=json.loads((ROOT/'config/analysis.json').read_text())
 db=out/'retail.duckdb';c=duckdb.connect(str(db))
 c.execute('CREATE OR REPLACE TABLE raw_lines AS SELECT * FROM read_csv(?,all_varchar=true)',[str(csv)])
 c.execute('CREATE OR REPLACE TABLE excluded_codes(code VARCHAR)');c.executemany('INSERT INTO excluded_codes VALUES (?)',[(s,) for s in cfg['exclude_codes']])
 c.execute('CREATE OR REPLACE TABLE settings(analysis_start VARCHAR,complete_end_exclusive VARCHAR,base_month VARCHAR,current_month VARCHAR)')
 c.execute('INSERT INTO settings VALUES (?,?,?,?)',[cfg[k] for k in ['analysis_start','complete_end_exclusive','base_month','current_month']])
 for file in sorted((ROOT/'sql').glob('0[123]_*.sql')):
  print('Executing',file.name,flush=True);c.execute(file.read_text())
 c.close(); print('Built',db,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--reextract',action='store_true');a=p.parse_args();build(a.output,a.reextract)
