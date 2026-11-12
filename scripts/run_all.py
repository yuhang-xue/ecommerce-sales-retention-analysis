"""Single reproducible entrypoint. Run from any working directory with the pinned environment."""
from pathlib import Path
import subprocess,sys,hashlib,json,platform
from datetime import datetime
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[1]
V=R/'validation';V.mkdir(exist_ok=True)
start=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
with (V/'run.log').open('w') as log:
 for command in [['build_analysis.py','--reextract'],['analyze.py'],['make_report.py'],['write_project_docs.py']]:
  line='RUN '+ ' '.join(command);print(line,flush=True);log.write(line+'\n');log.flush()
  r=subprocess.run([sys.executable,str(R/'scripts'/command[0]),*command[1:]],cwd=R,stdout=log,stderr=subprocess.STDOUT)
  if r.returncode:raise RuntimeError(f'{command[0]} failed; see validation/run.log')
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
files=[p for folder in ['sql','scripts','config'] for p in (R/folder).glob('*') if p.is_file() and not p.name.startswith('.')]
files += [R/'requirements.txt']
manifest={'started_at':start,'completed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'python':platform.python_version(),
'code_sha256':{str(p.relative_to(R)):digest(p) for p in sorted(files)},
'raw_workbook_sha256':digest(R/'data/raw/online_retail_II.xlsx'),
'export_sha256':{str(p.relative_to(R)):digest(p) for p in sorted((R/'data/exports').glob('*.csv')) if not p.name.startswith('.')},
'check_results':json.loads((R/'data/exports/analysis_summary.json').read_text())['checks_passed']}
(V/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Complete; see reports/ and validation/run_manifest.json',flush=True)
