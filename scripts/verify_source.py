"""Read-only verification of the official ZIP/XLSX using Python standard library.

Run from any directory: python3 scripts/verify_source.py
Writes a source manifest; does not clean or rewrite the workbook.
"""
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
import hashlib
import json
import posixpath
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
TAG = '{' + NS['s'] + '}'


def sha256(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def stamp(path):
    return datetime.fromtimestamp(path.stat().st_mtime, ZoneInfo('Asia/Shanghai')).isoformat()


def verify():
    archive = RAW / 'online_retail_ii.zip'
    with zipfile.ZipFile(archive) as package:
        assert package.testzip() is None, 'ZIP CRC validation failed'
        members = [n for n in package.namelist() if n.lower().endswith('.xlsx')]
        assert len(members) == 1, members
        workbook = RAW / Path(members[0]).name
        # Keep an existing extraction only if it is byte-identical to the archive.
        if workbook.exists():
            with package.open(members[0]) as source:
                assert hashlib.file_digest(source, 'sha256').hexdigest() == sha256(workbook)
        else:
            with package.open(members[0]) as source, workbook.open('wb') as dest:
                import shutil
                shutil.copyfileobj(source, dest)

    sheets = []
    with zipfile.ZipFile(workbook) as book:
        assert book.testzip() is None, 'XLSX CRC validation failed'
        shared = []
        if 'xl/sharedStrings.xml' in book.namelist():
            with book.open('xl/sharedStrings.xml') as stream:
                for _, elem in ET.iterparse(stream, events=('end',)):
                    if elem.tag == TAG + 'si':
                        shared.append(''.join(e.text or '' for e in elem.iter(TAG + 't')))
                        elem.clear()
        wb = ET.fromstring(book.read('xl/workbook.xml'))
        prop = wb.find('s:workbookPr', NS)
        is_1904 = prop is not None and prop.get('date1904') in ('1', 'true')
        epoch = datetime(1904, 1, 1) if is_1904 else datetime(1899, 12, 30)
        rels = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
        targets = {r.get('Id'): r.get('Target') for r in rels}
        for sheet in wb.find('s:sheets', NS):
            rid = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target = targets[rid]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            count = missing = invalid_dates = 0
            low = high = None
            headers = None
            with book.open(path) as stream:
                for _, row in ET.iterparse(stream, events=('end',)):
                    if row.tag != TAG + 'row':
                        continue
                    cells = {}
                    for cell in row.findall('s:c', NS):
                        col = ''.join(c for c in cell.get('r', '') if c.isalpha())
                        value = cell.findtext('s:v', default=None, namespaces=NS)
                        if cell.get('t') == 's' and value is not None:
                            value = shared[int(value)]
                        elif cell.get('t') == 'inlineStr':
                            value = ''.join(e.text or '' for e in cell.iter(TAG + 't'))
                        cells[col] = value
                    if headers is None:
                        headers = cells
                        date_col = next(k for k, v in headers.items() if v == 'InvoiceDate')
                        customer_col = next(k for k, v in headers.items() if v in ('Customer ID', 'CustomerID'))
                    elif any(v is not None and v != '' for v in cells.values()):
                        count += 1
                        if cells.get(customer_col) in (None, ''):
                            missing += 1
                        try:
                            serial = Decimal(cells[date_col])
                            low = serial if low is None else min(low, serial)
                            high = serial if high is None else max(high, serial)
                        except (KeyError, TypeError, ArithmeticError):
                            invalid_dates += 1
                    row.clear()
            def excel_date(value):
                return (epoch + timedelta(seconds=round(value * 86400))).isoformat(sep=' ') if value is not None else None
            sheets.append({'name': sheet.get('name'), 'data_rows': count, 'headers': headers,
                           'min_invoice_date': excel_date(low), 'max_invoice_date': excel_date(high),
                           'missing_customer_id_rows': missing, 'invalid_or_missing_date_rows': invalid_dates})
            print(json.dumps(sheets[-1], ensure_ascii=False), flush=True)

    metadata = json.loads((RAW / 'uci_dataset_502_metadata.json').read_text())['data']
    manifest = {
        'dataset': 'UCI Online Retail II', 'doi': '10.24432/C5CG6D',
        'source_url': 'https://archive.ics.uci.edu/dataset/502/online+retail+ii',
        'download_url': 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip',
        'download_completed_at': stamp(archive),
        'verified_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'verification': 'ZIP and XLSX CRC; full worksheet XML scan; SHA-256',
        'license': 'CC BY 4.0',
        'citation': 'Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.',
        'files': [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha256(p)}
                  for p in (archive, workbook, RAW / 'uci_dataset_502_metadata.json', RAW / 'uci_dataset_502_page.html')],
        'sheets': sheets,
        'total_data_rows': sum(s['data_rows'] for s in sheets),
        'official_num_instances': metadata['num_instances'],
        'metadata_has_missing_values': metadata.get('has_missing_values'),
        'official_webpage_has_missing_values': 'Yes',
        'missing_customer_id_rows': sum(s['missing_customer_id_rows'] for s in sheets),
        'note': 'Source API missing-value flag is not a substitute for measured data quality. Dates have no asserted timezone.'
    }
    assert manifest['total_data_rows'] == metadata['num_instances'], 'Official row count mismatch'
    (RAW / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    lines = [
        '# 数据来源与下载记录', '',
        f"下载完成时间：{manifest['download_completed_at']}（北京时间）。",
        f"核验时间：{manifest['verified_at']}（北京时间）。", '',
        '## 1. 来源与许可', '',
        '- 数据集：UCI Online Retail II。',
        f"- 官方页面：{manifest['source_url']}",
        f"- 下载地址：{manifest['download_url']}",
        '- 元数据接口：https://archive.ics.uci.edu/api/dataset?id=502',
        '- 许可：CC BY 4.0，https://creativecommons.org/licenses/by/4.0/ 。',
        f"- 推荐引用：{manifest['citation']}",
        '- 官方网页与API响应均保存到 raw 目录，原始工作簿未清洗、未改写。', '',
        '## 2. 文件清单与完整性', '',
        'ZIP及XLSX内部成员的CRC校验均通过；以下SHA-256用于本地版本固定和后续重跑校验。官方未提供可供比对的SHA-256，本地哈希不代表官方签名验证。', '',
        '| 文件 | 字节数 | SHA-256 |', '| --- | ---: | --- |',
    ]
    lines += [f"| `{f['name']}` | {f['bytes']:,} | `{f['sha256']}` |" for f in manifest['files']]
    lines += ['', '## 3. 工作簿实测信息', '',
              '通过逐行扫描工作表XML获得，行数不含表头，不等于订单数。时间取源数据原值，不作时区转换。', '',
              '| 工作表 | 数据行数 | 最早交易时间 | 最晚交易时间 | 客户ID缺失行数 | 缺失／无效日期行数 |',
              '| --- | ---: | --- | --- | ---: | ---: |']
    lines += [f"| {s['name']} | {s['data_rows']:,} | {s['min_invoice_date']} | {s['max_invoice_date']} | {s['missing_customer_id_rows']:,} | {s['invalid_or_missing_date_rows']:,} |" for s in sheets]
    lines += ['', f"合计 **{manifest['total_data_rows']:,}** 条数据记录，与官方API记录数一致。客户ID空值合计 **{manifest['missing_customer_id_rows']:,}** 行；此处只统计原始空值，不等于完成客户ID质量核查。", '',
              '实际表头：', '']
    lines += [f"- {s['name']}：" + '、'.join(f'`{v}`' for v in s['headers'].values()) + '。' for s in sheets]
    lines += ['', '字段映射应以实测表头建立：`Invoice` → `InvoiceNo`、`Price` → `UnitPrice`、`Customer ID` → `CustomerID`；其余字段按原名核对。原始层保留原字段，标准层才应用映射。', '',
              '## 4. 已发现的来源差异与使用限制', '',
              '- 官方网页标记存在缺失值（Yes），API的 `has_missing_values` 为 `no`；实测客户ID确有空值。两份快照保留，后续以文件体检为准，不能跳过缺失检查。',
              '- 两张工作表的日期范围在2010年12月1日至9日发生重叠。日期重叠尚不能证明具体交易重复；合并分析前必须检查跨表重复和订单键，不可直接把逐表金额相加作为最终结果，也不可未经核查按日期删掉一段。',
              '- 数据结束于2011年12月的月中，2011年12月不得直接作为完整月份进行环比、同比或完整月龄复购比较。其他月份仍需核查每日覆盖，不能仅凭起止日期认定完整。',
              '- 本次仅完成下载、完整性与结构核验，以及客户ID空值计数；重复、取消、负数量、非正价格、异常大额、订单键和业务指标尚未分析。', '',
              '## 5. 本次数据准备验收', '',
              '| 编号 | 状态 | 实测证据 |', '| --- | --- | --- |',
              '| A01 | 通过 | 官方来源与许可快照、文件SHA-256已记录；本地哈希复核见清单 |',
              '| A02 | 通过 | ZIP/XLSX CRC无错误；逐表扫描行数合计与官方记录数一致 |',
              '| A03 | 通过 | 每张工作表的表头和日期范围已记录 |', '',
              '执行方式：Codex通过本地Python脚本核验。A04—A28与E01—E03未执行；以上通过状态不代表项目最终验收通过。', '',
              '复核命令（在项目根目录执行）：', '', '```bash', 'python3 scripts/verify_source.py', '```', '',
              '机器可读证据：[source_manifest.json](raw/source_manifest.json)。正式验收标准见[任务验收文档](../docs/任务验收文档.md)。', '']
    (ROOT / 'data' / '数据来源与下载记录.md').write_text('\n'.join(lines))
    print('Saved data/raw/source_manifest.json', flush=True)


if __name__ == '__main__':
    verify()
