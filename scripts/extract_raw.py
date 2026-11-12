"""Lossless source-value extraction: XML numeric/text values, plus source row identity."""
from pathlib import Path
import csv, zipfile, xml.etree.ElementTree as ET, json, hashlib
ROOT=Path(__file__).resolve().parents[1]
TAG='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def extract(output=None):
    output=Path(output or ROOT/'data/processed/raw_lines.csv')
    output.parent.mkdir(parents=True,exist_ok=True)
    source=ROOT/'data/raw/online_retail_II.xlsx'
    expected=json.loads((ROOT/'data/raw/source_manifest.json').read_text())
    with source.open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==next(x['sha256'] for x in expected['files'] if x['name']==source.name)
    count=0
    with zipfile.ZipFile(source) as z, output.open('w',newline='') as out:
        strings=[]
        with z.open('xl/sharedStrings.xml') as f:
            for _,e in ET.iterparse(f,events=['end']):
                if e.tag==TAG+'si': strings.append(''.join(x.text or '' for x in e.iter(TAG+'t'))); e.clear()
        writer=csv.writer(out)
        writer.writerow(['source_file','source_sheet','source_row','Invoice','StockCode','Description','Quantity','InvoiceDate','Price','Customer ID','Country'])
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        pr=wb.find(TAG+'workbookPr'); assert pr is None or pr.get('date1904') not in ('1','true')
        rels={e.get('Id'):e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in wb.find(TAG+'sheets'):
            target=rels[sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            with z.open(target) as f:
                for _,e in ET.iterparse(f,events=['end']):
                    if e.tag!=TAG+'row': continue
                    vals={}
                    for c in e.findall(TAG+'c'):
                        col=''.join(x for x in c.get('r') if x.isalpha())
                        v=c.findtext(TAG+'v')
                        if c.get('t')=='s' and v is not None: v=strings[int(v)]
                        elif c.get('t')=='inlineStr': v=''.join(x.text or '' for x in c.iter(TAG+'t'))
                        vals[col]=v
                    if int(e.get('r'))>1 and any(v not in (None,'') for v in vals.values()):
                        writer.writerow([source.name,sh.get('name'),e.get('r')]+[vals.get(c) for c in 'ABCDEFGH']); count+=1
                    e.clear()
    assert count==expected['total_data_rows']
    print(f'Extracted {count:,} source rows -> {output}',flush=True)
    return output
if __name__=='__main__': extract()
