# 电商销售波动与用户复购分析

已完成实施方案第1-10节的分析与文档交付。使用UCI Online Retail II公开历史数据，完成质量核查、DuckDB SQL建模、销售变化分解、复购队列、敏感性分析与8页报告。**Tableau看板已制作，在线发布尚未确认。**

## 先看结果

- [PDF报告（8页，含封面与目录）](reports/电商销售波动与复购分析报告.pdf)／[可编辑Markdown报告](reports/电商销售波动与复购分析报告.md)
- [原方案与执行状态](数据分析作品_电商销售波动与复购分析.md)
- [数据质量报告](docs/数据质量报告.md)、[指标字典](docs/指标字典.md)、[专题与方法](docs/专题选择与方法说明.md)
- [图表追溯](docs/图表与数据追溯.md)、[任务验收](docs/任务验收文档.md)
- [简历与面试材料](docs/简历与面试材料.md)、[扩展边界与后续清单](docs/扩展边界与后续清单.md)

2011年11月相比2010年11月，商品正向金额增长1.54%，已识别客户金额下降1.70%；排除最高约1%大额订单后，全量同比变为-3.40%。这是描述性分析，不能据此断言业务原因或已实现运营收益。

## 从原始数据完整复现

要求Python 3.13（本次实测版本见 `validation/run_manifest.json`）。使用虚拟环境，不需要PostgreSQL服务、Excel或Tableau。以下在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# 首次克隆后下载官方原始数据（约46 MB）
curl -fL 'https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip' -o data/raw/online_retail_ii.zip
python scripts/verify_source.py
python scripts/run_all.py
```

完整运行会重新提取官方XLSX，重建派生表、CSV、图表、PDF和数据分析文档；原始文件不变。约1分钟至数分钟，取决于磁盘与机器；首次依赖安装另计。生成结果覆盖派生目录中的同名文件，不重复追加记录。不要在DuckDB写入时同时运行另一份流水线。

报告需要中文TrueType字体。macOS默认使用 `/System/Library/Fonts/Supplemental/Songti.ttc`。其他系统安装支持中文的TTF字体，设置后运行：

```bash
export RETAIL_CJK_FONT='/path/to/chinese-font.ttf'
python scripts/run_all.py
```

字体环境变量仅影响报告排版，分析数据不依赖系统中文字体。图表与PDF在本机已渲染检查；其他系统仍应检查字体显示。

入口执行顺序：

1. `scripts/build_analysis.py --reextract`：核对工作簿SHA-256、读取XML原值、建立DuckDB，执行SQL 01-03。
2. `scripts/analyze.py`：执行SQL 04-05，导出指标／贡献／队列，进行独立复算与敏感性检查。
3. `scripts/make_report.py`：用导出结果生成图表、8页PDF与Markdown报告。
4. `scripts/write_project_docs.py`：生成质量报告、指标字典、方法、追溯与面试材料。

每一步均可独立运行，前置产物须先生成。详细日志在 `validation/run.log`，代码与输出哈希在 `validation/run_manifest.json`。验收状态文件保留本次人工检查记录，不由流水线自动把看板或真人演示标为通过。

## GitHub仓库内容

仓库保留分析代码、SQL、汇总数据、报告、图表和核查结果。原始ZIP/XLSX、大型派生数据库、逐行明细和临时文件不纳入Git，可按上述步骤下载并重建。

Tableau工作簿：[`电商经营概览.twbx.twb`](电商经营概览.twbx.twb)。该文件为TWB工作簿定义，不是包含数据的TWBX打包文件；打开后需重新连接本地生成的CSV数据。`outputs/`中的图片是设计预览，不代表已发布的在线看板。

## 结果位置

| 路径 | 内容 |
| --- | --- |
| `data/raw/` | 官方ZIP、原始XLSX、来源清单、官方快照 |
| `data/processed/raw_lines.csv` | 全部原始XML字符串值与来源行号，可重新生成 |
| `data/processed/retail.duckdb` | raw_lines、clean_lines、order_summary、customer_month、metric_month等派生表 |
| `data/exports/` | 月度指标、质量、分组贡献、因素贡献、复购、敏感性及分析摘要 |
| `data/exports/sales_lines.csv` | 后续看板可用的有效商品正向明细；包含不完整尾月，需按字典筛选 |
| `sql/` | 分层建模、月指标／窗口函数、质量、贡献和独立对账SQL |
| `validation/` | 检查结果、异常样例、候选匹配、独立环境复现结果和PDF预览 |
| `reports/` | 8页PDF、Markdown和PNG图表 |

同源派生表不等于企业多系统数据整合。客户数不可跨月直接相加；明细、月汇总与队列表不能随意连接。具体粒度和空值规则见指标字典。

## 数据与分析版本

主口径保留有效商品正向交易，排除22,523条证实的跨表副本；保留表内重复并做敏感性。完整月窗口为2009-12至2011-11。所有原始记录均可追溯，原始文件不改写。报告文字针对v1的11月同比专题，脚本会检查核心范围和金额，避免换配置后静默沿用旧结论；改专题需同步更新报告文字与验收。

来源校验可单独运行 `python scripts/verify_source.py`。这会更新来源清单的核验时间和下载阶段说明，不等于完整分析重跑；若作为新数据版本使用，须重新执行完整流水线。

本次独立虚拟环境从复制的原始文件重跑，并按导出文件哈希比较，结果见 `validation/reproducibility.json`。自动分析检查见 `validation/checks.csv`；具体通过数以当前文件为准。

## 来源与许可

Chen, D. (2012). *Online Retail II* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。[下载记录](data/数据来源与下载记录.md)保留官方来源与哈希；派生数据处理规则见[口径变更记录](docs/口径变更记录.md)。
