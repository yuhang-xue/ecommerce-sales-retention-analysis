"""Write factual analysis documentation from generated evidence. No invented business outcomes."""
from pathlib import Path
import json
import pandas as pd,duckdb
R=Path(__file__).resolve().parents[1];D=R/'docs';E=R/'data/exports';V=R/'validation'
S=json.loads((E/'analysis_summary.json').read_text());c=duckdb.connect(str(R/'data/processed/retail.duckdb'),read_only=True)
def table(df):
 def fmt(x):
  if pd.isna(x):return 'NULL'
  if isinstance(x,float):return f'{x:,.6f}'.rstrip('0').rstrip('.')
  return str(x).replace('|','／').replace('\n',' ')
 return '| '+' | '.join(df.columns)+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(fmt(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))
def query(q):return c.execute(q).fetchdf()
def write(name,text):(D/name).write_text(text.strip()+'\n')
quality=pd.read_csv(E/'quality_summary.csv');qm=pd.read_csv(E/'quality_month.csv');matches=pd.read_csv(V/'cancel_match_summary.csv')
flags=query('''SELECT '客户ID缺失' issue,count(*) rows,sum(line_amount) signed_amount FROM clean_lines WHERE NOT cross_sheet_duplicate AND customer_id IS NULL
UNION ALL SELECT '取消标记',count(*),sum(line_amount) FROM clean_lines WHERE NOT cross_sheet_duplicate AND is_cancelled
UNION ALL SELECT '负数量',count(*),sum(line_amount) FROM clean_lines WHERE NOT cross_sheet_duplicate AND qty<0
UNION ALL SELECT '零单价',count(*),sum(line_amount) FROM clean_lines WHERE NOT cross_sheet_duplicate AND unit_price=0
UNION ALL SELECT '负单价',count(*),sum(line_amount) FROM clean_lines WHERE NOT cross_sheet_duplicate AND unit_price<0
UNION ALL SELECT '表内额外重复',count(*),sum(line_amount) FROM clean_lines WHERE NOT cross_sheet_duplicate AND within_sheet_occurrence>1''')
flags.to_csv(V/'canonical_quality_flags.csv',index=False)
no_days=query('SELECT weekday,count(*) AS no_record_days FROM daily_coverage WHERE canonical_rows=0 GROUP BY weekday ORDER BY weekday')
descriptions=len(pd.read_csv(V/'description_changes.csv'))
write('数据质量报告.md',f'''
# 数据质量报告

版本1.0；数据处理日期：{S['generated_at'][:10]}。本报告基于实际文件，范围为全部原始记录（含不完整尾月），与专题分析的完整月窗口区分。

## 1. 来源、粒度与处理总账

来源与文件哈希见[下载记录](../data/数据来源与下载记录.md)。一行是发票内商品／费用／调整明细，不是一个订单。raw_lines保存原始8字段的XML字符串值及文件、工作表、行号；Excel日期序列仅在标准层转换为时间戳。原始工作簿没有改写。

原始1,067,371行，标准层仍为1,067,371行；处理分类互斥，合计等于原始行数。排除跨表副本后保留1,044,848条来源明细。以下金额均为各类记录的数量×单价带符号合计，不是会计收入：

{table(quality)}

正向购买与取消分别统计。商品有符号记录金额是正向商品记录与同范围负向商品记录之和，仅为记录层净额，不证明退款到账，也不作为三因素分解的金额。

## 2. 跨表与表内重复

两张表在2010-12-01至2010-12-09重叠。22,202种完全相同的8字段组合在两表同时出现，副本共22,523行，逐组合重复次数差为0。日期分布也一致。主分析保留后一张表（Year 2010-2011），前表相同记录仅标记排除，原始值不删除。追溯见 `validation/cross_sheet_evidence.csv`、`duplicate_samples.csv`。

保留表内多次出现的同值记录，不能仅凭全字段相同断定录入错误。主分析中额外表内重复11,812行，商品正向金额影响57,092.82 GBP；另给出全字段去重敏感性。以signature匹配时保留来源行号与表内出现序号，不把整张表某段日期粗暴删除。

## 3. 缺失、取消与非正价格

下表已排除跨表副本；各质量标记可以重叠，不能把行数或金额相加当总问题规模：

{table(flags)}

原始客户ID空值243,007行。有效正向商品金额允许缺失客户ID；人数、频次、已识别客单价与复购排除缺失客户，不生成伪客户nan／空串。各月覆盖率与金额影响见下表；分母是同月全部有效正向商品记录，而非全部原始行：

{table(qm[['month','canonical_rows','missing_customer_rows','positive_rows','known_positive_rows','positive_amount','unknown_positive_amount']])}

取消标记、负数量和非正价格的交叉情况见 `validation/flag_intersections.csv`。原始数据有1条取消标记但数量为正、5条负价记录，均保留并按业务类别排除主分析；非正价格不能被自动当作普通销售。商品零价可为赠品或库存调整，现有数据不能确认原因，主口径排除并保留证据。零价与负价涉及的编码、描述和原始样例可从数据库与quality_samples追溯。

## 4. 非商品编码与商品描述

人工阅读编码及描述后，将POST、DOT、C2、C3、D、S、BANK CHARGES、M（含小写m）、ADJUST、ADJUST2、AMAZONFEE、CRUK、B、TEST001、TEST002及GIFT_前缀列入排除清单，分别对应运输费用、折扣／费用／调整、测试或礼券。不是按数字正则强行过滤，DCGS等真实商品编码仍可纳入。完整影响表见 `validation/non_merchandise_codes.csv`，规则见 `config/analysis.json`。

{descriptions:,}个商品编码存在多个原始描述，商品聚合以StockCode为键，不以描述关联。1条商品编码有首尾空格；描述有213,035行首尾空格，原始描述保留，展示时可去除空格。客户ID均为数字文本或缺失，标准层保留字符串。`text_audit.csv`和`description_changes.csv`记录全部结果。

原始单价含1E-3（0.001 GBP），不能统一按分截断。标准价格用DECIMAL(18,6)、行金额DECIMAL(24,6)；用Python Decimal从原始价格重算所有行，在百万分之一GBP上与SQL精确一致，报表显示时才四舍五入。

## 5. 订单键与关联

同一Invoice未发现跨客户、跨国家或跨自然日；也没有同发票同时出现客户缺失和非缺失。少量同发票包含多个同日时间戳，记录在 `order_time_variation.csv`，不拆成不同订单。采用标准化发票号作为订单键，汇总时间取最早时间。

order_summary每发票一行；customer_first每已识别客户一行；purchase_lines左连customer_first后，正向明细行数与金额均保持一致。复核见 `checks.csv`。商品多选必须COUNTD订单，不能把分商品订单数相加。

## 6. 取消候选匹配的边界

只对商品取消记录，按客户ID＋商品编码＋相同单价＋绝对数量匹配此前正向明细；不要求同一发票号，不匹配未来记录，不限制最大间隔。结果仅描述候选数量，没有分配原单、没有证明一对一退款：

{table(matches)}

无客户ID单列。只有1个候选明细的取消记录为4,713条，占17,974条商品取消记录的26.22%；至少1个候选为6,137条（34.14%）。多个取消可能竞争同一购买明细，因此唯一候选也不是已验证退款。记录金额、时间与候选数见 `cancellation_candidates.csv`。不将未匹配记录当错误删除。

## 7. 时间覆盖

2009-12-01至2011-12-09有原始记录，所有日期可解析。分析主窗口为2009-12-01至2011-12-01（右端不含），共24个完整自然月；保留2011年12月原始和派生数据，但不做完整月同比／环比、完整月龄复购。

无记录日分布：

{table(no_days)}

周六全部无交易记录，其他空档集中在部分周日、年末及节假日前后；没有营业日历，不能证明停业或数据丢失。daily_coverage逐日保留0记录标记。两期专题11月均30个自然日、26个有正向购买记录日；仍存在无法独立确认覆盖完整性的限制。

## 8. 大额与敏感性

固定阈值为完整分析期订单金额99分位数{S['extreme_order_threshold']:,.4f} GBP，超过阈值按整单排除；不是认定这些订单无效。2010年11月30笔大额订单金额308,180.71 GBP，2011年11月50笔368,609.91 GBP。

{table(pd.read_csv(E/'sensitivity.csv'))}

主口径全量同比+1.54%，仅表内去重+1.57%，剔除大额后-3.40%。增长方向对大额订单敏感，对表内重复处理较稳定。商品前10贡献排名的变化见 `validation/sensitivity_product_ranks.csv`；报告不以单一排名推断供给或营销原因。跨表去重对本次11月专题无影响，但影响重叠的2010年12月及全期金额，逐月见 `monthly_signed_bridge.csv`。

## 9. 处理决定

全部问题已给出可执行处理与局限；不把无法确认的业务原因写成事实。自动计算检查见 `validation/checks.csv`，最终分析范围验收与第11节延后项见[任务验收文档](任务验收文档.md)。
''')
write('指标字典.md','''
# 指标字典

版本1.0；数据来源：UCI Online Retail II；计价GBP。正式实现：`sql/01_clean.sql`、`02_metrics.sql`、`04_contributions.sql`及`scripts/analyze.py`。

## 1. 统一范围与精度

- 原始记录：所有工作表全部非空数据行，共1,067,371行。原始8字段保留XML字符串值。
- 规范记录：排除已证实的跨表相同副本，保留表内重复和原始质量标记。
- 商品口径：排除配置中的非商品、费用、调整、测试和礼券编码；未确认的业务原因不填补。
- 有效正向购买：record_type='positive_purchase'，非取消、数量>0、单价>0且必要字段有效。
- 已识别客户范围：有效正向购买且CustomerID非NULL；所有客户分解因子用同一范围。
- 完整分析窗口：2009-12-01 ≤ InvoiceDate < 2011-12-01。完整指源文件首尾边界上的自然月完整，不证明每日无记录一定是停业。原始时区未知，不转换。
- 日期筛选采用左闭右开；订单键为trim后的Invoice；同发票同日多个时间戳不拆单。
- 单价DECIMAL(18,6)，金额DECIMAL(24,6)；0.001保留，不能逐行按分提前舍入。计数为整数，比例保存0到1；分母为0返回NULL。

## 2. 业务指标

| 指标 | 公式／条件 | 粒度与分母 | 适用限制 |
| --- | --- | --- | --- |
| 全量商品正向金额 | SUM(LineAmount) WHERE IsValidPurchase | 交易明细可加总，GBP | 包含客户ID缺失，不等于收入／利润 |
| 已识别客户商品正向金额 | 上述金额再要求CustomerID非NULL | 同一客户分析范围，GBP | 三因素分解唯一使用此金额 |
| 商品有符号记录金额 | 正向商品＋商品取消／其他负向商品记录的带符号金额 | 记录层聚合，GBP | 不称会计净收入或真实退款净额；不用于乘法分解 |
| 购买订单数 | COUNT(DISTINCT OrderKey) WHERE IsValidPurchase | 筛选范围内订单 | 不能跨商品求和；订单跨月已核查不存在 |
| 已识别购买订单数 | 有效购买且CustomerID非NULL的去重订单 | 客户分析范围内订单 | 与已识别金额一致 |
| 购买客户数 | COUNT(DISTINCT CustomerID) WHERE IsValidPurchase | 筛选范围内非空客户 | 不能跨月求和 |
| 人均购买频次 | 已识别购买订单数／购买客户数 | 每位已识别客户订单数 | 零客户为NULL |
| 全量客单价 | 全量商品正向金额／购买订单数 | GBP／订单 | 非行金额平均值 |
| 已识别客单价 | 已识别客户商品正向金额／已识别购买订单数 | GBP／已识别客户订单 | 用于三因素分解 |
| 金额识别覆盖率 | 已识别客户商品正向金额／全量商品正向金额 | 相同时间与筛选范围 | 不表示客户人数覆盖率 |
| 正向明细识别覆盖率 | 已识别客户有效正向行数／全部有效正向行数 | 交易明细行数 | 与金额覆盖率分别披露 |
| 环比／同比 | 本期金额／上期或去年同月金额 - 1 | 同一口径的完整自然月 | 基期0或未完整观察返回NULL；同比使用12个月滞后 |
| 首次观测购买月 | MIN(月份) OVER 客户完整可用正向历史 | 每客户唯一 | 不是客户真实首购，不随展示日期筛选重算 |
| 月度新客金额 | 购买月=首次观测购买月的客户金额 | 交易月份 | 不称真实获客金额 |
| 月度老客金额 | 购买月>首次观测购买月的客户金额 | 交易月份 | 跨月同一客户可贡献两类月份 |
| 未知客户金额 | CustomerID为NULL的有效商品正向金额 | 交易月份 | 不强行归入新老客 |
| 月龄k复购率 | 首次观测队列在第k个自然月再次购买人数／原队列人数 | 队列月×月龄，k≥1 | 非累计；同客户同月只计一次；未完整观察为NULL |
| 次月复购率 | 上述k=1 | 次月完整观察队列 | 合并队列按人数加权，只在相同月龄合并 |
| 分组金额变化贡献 | 本期组金额 - 基期组金额 | 商品／国家／客群各维度独立 | 全分组加总等于对应范围总变化；Top N需补其他 |
| 三因素贡献 | 对人数、频次、客单价全部6种替换顺序求边际贡献均值 | 两个同范围完整期间 | 描述性Shapley分解，非因果归因 |

## 3. 表与字段

| 表 | 一行代表什么 | 键／重要字段 |
| --- | --- | --- |
| raw_lines | 一条原始XML明细 | source_file、source_sheet、source_row；原8字段 |
| standard_lines／clean_lines | 一条原始明细加标准值、标记和分类 | line_id唯一；signature用于8字段相同性；within_sheet_occurrence、cross_sheet_duplicate、record_type |
| order_summary | 一笔有效正向商品订单 | order_key唯一；order_ts、month、customer_id、country、amount |
| customer_first | 一个有效已识别客户 | customer_id唯一；first_month |
| customer_month | 一个客户在一个月的购买 | customer_id＋month唯一；orders、amount、first_month |
| metric_month | 一个月的全量与已识别指标 | month唯一；amount、orders、customers、known_orders、known_amount、frequency、aov、known_aov、identified_amount_coverage |
| cohort_cells | 一个首次观测月×月龄 | first_month＋month_age唯一；cohort_size、returning_customers、complete_observation |
| group_contributions | 一个维度中的一个组 | dimension＋group_name；base_amount、current_amount、contribution |

## 4. 导出数据字典

`sales_lines.csv`每行一条有效正向商品明细，保留所有源时间（包括2011年12月不完整尾月）。默认分析必须筛选InvoiceDate<2011-12-01，不能把尾月当完整月。字段：LineID、OrderKey、CustomerID、InvoiceDate、Month、StockCode、Description、Country、Quantity、UnitPrice、LineAmount、IsValidPurchase、FirstObservedMonth、CustomerType。

CustomerID空值写为空字段，导入时应设为NULL而非字符串或0；OrderKey、StockCode、CustomerID设为字符串。IsValidPurchase导出true／false；日期字段按时间／日期导入。CSV不能携带类型约束，准确类型以数据库为准。此文件不是完整清洗表，取消和其他调整在数据库clean_lines与质量统计中保留。

`metric_month.csv`是月汇总，不能直接相加得到跨月客户数；`cohort_cells.csv`是队列单元格，不与明细物理连接；`period_contribution.csv`只支持预定义11月同比；`quality_summary.csv`是全源范围互斥分类，分母为1,067,371原始行。Tableau连接与交互测试留待第11节。
''')
write('专题选择与方法说明.md',f'''
# 专题选择与方法说明

## 1. 从趋势到问题

先计算24个完整自然月的金额、订单、客户与识别覆盖率，结果见 `data/exports/metric_month.csv`。两年年末均有上升，不把旺季环比称为异常。选择最新完整旺季月份2011年11月，与2010年11月同月同比，检查“总额微增是否反映客户经营普遍改善”。选择依据是时间完整、同季节与全量／已识别趋势分歧，而不是挑一个已预设的下滑。

两期均30个自然日、26个有正向购买记录日。数据没有营业日历，仅两年历史，无法全面控制工作日结构、外部环境或促销差异。

## 2. 数值分解

全量商品正向金额变化22,065.408 GBP；已识别客户变化-19,708.642 GBP，未知客户变化41,774.05 GBP，两者合计闭合。已识别范围使用人数×频次×客单价，Shapley对6种替换顺序的边际贡献取均值，不预设先替换哪个因素。因子值和贡献见 `factor_contributions.csv`；频次与客单价不混入未知客户订单。

商品、国家、新老客（含未知）各维度独立拆解同一全量金额差额。商品／国家图按绝对贡献前7项展示，保留其他。不存在基期交易的组只列绝对贡献，不输出无穷增长率，更不推断新品上市。商品名称是展示属性，不是连接键。

## 3. 敏感性与集中度

在看结果之前固定方法：全完整分析期正向订单金额99分位阈值，所有比较期共用，整单排除。实测阈值{S['extreme_order_threshold']:,.4f} GBP。主口径保留大额及表内重复，敏感性包括仅表内去重、仅排除大额、两者同时、纳入非商品正向记录、不做跨表排重。

主结论限定为“总额微增且对大额敏感”。剔除大额后方向翻转；这不证明大额订单应删除，而是提示批发和集中度必须进入解释。商品贡献排名的场景变化见 `validation/sensitivity_product_ranks.csv`。

## 4. 复购方法

完整正向历史上求首次观测月；每客户每月去重一次；月龄按自然月差。固定观察截止为2011-12-01（右端不含）。月龄0仅为队列基线，所有未完整观察单元格为NULL；完整且无人回购为0。报告热力图展示月龄1-12，并保留完整CSV的0-24月龄。

比较2010、2011年1-10月首次观测队列的次月复购，均有完整次月；加权分母为各队列人数之和。不跨不同月龄加总。原始首月混入历史客户，历史累积导致后续队列结构变化，故不同年份对比只是描述，不声称触达或留存效果。

## 5. 分析与因果的界限

本项目建立描述性恒等分解和分组关系。缺失ID变化不能直接归因采集故障，客单价下降不能直接归因降价，商品金额下降不能直接归因缺货。每条建议均需补充数据或实验才能验证。
''')
write('图表与数据追溯.md','''
# 图表与数据追溯

所有图由`scripts/make_report.py`读取下列计算文件生成；报告PDF与Markdown同源。金额GBP，图中万GBP仅为显示缩放，未改写底层金额。报告默认范围固定，后续交互筛选时静态结论不应直接复用。

| 图／报告位置 | 输入文件 | 计算入口 | 样本与分母 | 核对证据 |
| --- | --- | --- | --- | --- |
| 01_monthly_trend／第3页 | metric_month.csv | sql/01_clean.sql、02_metrics.sql | 2009-12至2011-11，金额全量商品；客户为已识别 | independent_monthly_differences.csv |
| 02_coverage／第2页 | metric_month.csv | sql/02_metrics.sql | 已识别商品正向金额／全量同口径金额 | quality_month.csv、checks.csv |
| 03_factor_waterfall／第3页 | factor_contributions.csv | scripts/analyze.py、analysis_utils.py | 2010-11与2011-11，已识别范围 | shapley_closure、factor_identity检查 |
| 04_group_contributions／第4页 | group_contributions.csv | sql/04_contributions.sql | 同期全量商品金额，前7组＋其他 | group_closure_product／country／customer_type |
| 05_cohort_heatmap／第5页 | cohort_cells.csv | sql/02_metrics.sql | 已识别首次观测队列，月龄1-12；分母原队列规模 | independent_cohort_counts及边界检查 |
| 06_sensitivity／第1页 | sensitivity.csv | scripts/analyze.py | 两期相同商品口径；固定订单99分位阈值 | sensitivity_product_ranks.csv、top_orders.csv |
| 第1页指标表 | metric_month.csv | sql/02_metrics.sql | 两个11月 | independent_monthly_differences.csv |
| 第2页质量表 | quality_summary.csv | sql/03_quality.sql | 全部1,067,371原始行，互斥分类 | raw_row_conservation、monthly_signed_bridge.csv |
| 第4页新老客 | group_contributions.csv | sql/04_contributions.sql | 首次观测月定义，未知客户单列 | group_closure_customer_type |
| 第5页次月比较 | cohort_comparison.csv | scripts/analyze.py | 每年1-10月队列；相同月龄1按人数加权 | 独立队列复算 |
| 第5页高频客户 | frequency_segments.csv | scripts/analyze.py | 完整期累计10笔及以上；分母已识别金额 | customer_month_amount |

查询按数字顺序执行；04在analyze阶段执行。CSV默认位于data/exports，检查结果位于validation。`sales_lines.csv`留作后续看板输入，不代表看板已创建。
''')
write('简历与面试材料.md','''
# 简历与面试材料

定位：公开数据个人项目，使用2009-2011年UCI历史交易。以下表述基于已完成计算；实际投递前应确认自己能解释并重跑对应SQL，不将辅助完成的工作虚构为企业实习或独立经营成果。Tableau尚未制作，不写已发布看板。

## 1. 四条简历表述

- 基于UCI Online Retail II的106.7万条交易明细，使用Python与DuckDB SQL建立原始、标准、订单、客户月和月度指标层；识别并处理22,523条跨表副本，保留缺失、取消及表内重复的质量标记和处理影响。
- 统一商品正向金额、购买订单、客户、频次与客单价口径，分析2011年11月同比：全量金额增长1.54%，已识别客户金额下降1.70%；用Shapley分解识别客单价因素贡献约-5.15万GBP。
- 按首次观测购买月建立复购队列，区分完整观察与未到期单元格；在可比次月窗口中，计算2010和2011年1-10月队列加权复购率20.49%与23.60%，说明历史缺失及客群结构限制。
- 完成6页分析报告、SQL/Python复现流程与独立数值核对；发现排除最高约1%订单后同比转为-3.40%，提出客户ID覆盖、大额订单及商品结构核查方案，不将建议表述为已实现经营收益。

## 2. 三分钟讲述稿

**0:00-0:30，问题和数据。** 我用UCI英国零售商公开历史交易分析销售变化与复购。数据有106.7万条明细，明细不等于订单。主分析使用24个完整自然月，重点比较2011年11月与2010年11月。

**0:30-1:10，先解决可信度。** 两张表的重叠区间有22,523条完全相同副本，我保留后一表，原始层不删除。同表重复没有证据证明错误，所以主分析保留、另做敏感性。金额可以包含客户ID缺失，但客户拆解必须用已识别范围。

**1:10-2:00，发现和证据。** 全量商品正向金额同比增长1.54%，已识别客户金额却下降1.70%，未知客户金额增长解释了差异。三因素分解显示人数增长贡献约3.81万GBP，频次和客单价分别贡献-0.63万和-5.15万GBP。剔除最高约1%的大额订单后，总额同比转为-3.40%，说明增长不是稳健的普遍改善信号。

**2:00-2:35，复购。** 我按首次观测购买月分队列，并只比较完整月龄。2011年1-10月队列的加权次月复购率23.60%，2010年同期20.49%。首次观测不是真实首购，历史累积改变客群结构，所以不能说运营改善导致复购提升。

**2:35-3:00，建议和边界。** 我会优先补充订单来源和客户映射，核查大额及未知客户；再结合价格、库存和促销资料检查客单价。建议尚未实施，没有宣称销售额提升。完整SQL、检查和报告可以复现。

这是一份约3分钟的讲述稿，不代表已完成真人演练或用户能力验收。

## 3. 面试问答

**为什么不直接删除缺失客户？** 缺失影响客户识别，但不必然使交易金额无效。全量有效商品金额保留；客户指标排除，并披露金额和行数覆盖率。

**为什么删跨表重复、不删同表重复？** 重叠区间8字段完全一致且每种组合出现次数相同，支持重复收录的处理；同表可能是合法重复明细，缺乏业务唯一行ID，所以不默认删除。

**取消记录如何处理？** 负向商品记录单列，不进入购买订单和三因素正向金额。精确条件匹配只提供候选，唯一候选也不能证明真实退款链路；没有支付和退款流水。

**订单键为什么只用发票号？** 全量核查未发现同发票跨客户、国家或日期，少数同日时间差保留。来源表不能直接拼入订单键，否则重叠区间会重复计单。

**如何避免关联重复累计？** 先验证customer_first每客户唯一，再左连明细；比较关联前后行数与金额；订单表按发票唯一；月度汇总和队列表不物理连接到明细。

**为什么选择同比？** 两年年末都有旺季，直接环比容易混入季节差异。最新完整11月对上年同月，两期天数与有交易日数一致，但仍不足以控制所有外部因素。

**为什么用Shapley？** 人数×频次×客单价存在交互，固定替换顺序会改变贡献。我平均全部6种顺序，保证贡献和等于金额变化；它仍是描述分解，不是因果估计。

**大额订单应该删除吗？** 不应默认删除，批发业务可以合理产生大额。主分析保留；统一阈值敏感性展示结论对集中度的依赖。

**复购分母怎么定？** 首次观测月的客户人数固定；第k月去重回购人数做分子。展示日期不能重定义首购，未完整观察为NULL，真实无人回购为0。

**如何验证建议？** 数据核查用覆盖率、订单分层同比和对账；营销触达需额外数据及随机实验，提前定义回购率、样本量和毛利等护栏，当前数据不能直接完成验证。
''')
write('扩展边界与后续清单.md','''
# 扩展边界与后续清单

## 本次已完成

实施方案第1-10节的可执行分析成果：数据体检、口径、分层SQL、描述性贡献分解、队列复购、敏感性、6页报告、复现说明、验收证据、简历与面试材料。

## 第11节留待后续

Tableau工作簿、经营概览及另外两页看板、筛选联动、浏览器显示检查、公开发布及链接均未制作或验证。分析CSV已就绪，但看板交互验收不能因此标为通过。对应A21-A24、A27、A28的看板与演示部分、E01-E03保留待执行。

## 数据不足时需要补充什么

| 扩展目标 | 需要新增数据 | 本数据不能支持的结论 |
| --- | --- | --- |
| 订单支付／退款对账 | 订单ID、支付流水ID、退款ID、金额与状态、关联键 | 取消一定等于退款到账 |
| 履约与库存 | 订单商品、出库、物流节点、库存、缺货、交付时间 | 销售下降由缺货或物流导致 |
| 营销转化 | 曝光、点击、会话、渠道、投放成本、归因窗口 | 完整转化漏斗和渠道ROI |
| 利润与定价 | 成本、税费、折扣明细、运费承担方 | 净利润或降价的因果影响 |
| 真实新客与留存 | 更长购买历史、稳定客户映射、触达和实验分组 | 首次观测客户都是真新客，复购变化来自运营 |

不篡改真实数据制造“脏数据”。边界验证仅在内存中使用独立小型模拟例子，标记为synthetic，不写入raw_lines或业务输出。若需要多系统SQL展示，应另选真实可关联的多表数据。
''')
write('口径变更记录.md','''
# 口径变更记录

| 版本／编号 | 原规则或状态 | 本次决定 | 依据及影响 | 重跑范围 |
| --- | --- | --- | --- | --- |
| v1.0 / D01 | 跨表重复待核查 | 保留后一表同值副本，保留表内重数 | 重叠期22,523副本，逐8字段组合次数一致 | 全部SQL、指标、复购和报告 |
| v1.0 / D02 | 正向销售范围待冻结 | 以商品口径为主，排除费用／调整／测试／礼券代码 | 非商品编码描述可核查；另列包含这些正向金额的敏感性 | 金额、订单、客户、全部分析 |
| v1.0 / D03 | 订单键待验证 | 标准化Invoice作为键 | 无跨客户／国家／日期冲突，同日时间差不拆单 | 订单及下游 |
| v1.0 / D04 | 完整期间待确定 | 主窗口截至2011-11，尾月保留但不比较 | 2011-12只有到9日；两期专题11月均30天、26个有购买日 | 月度比较与队列观察 |
| v1.0 / D05 | 调整后金额待核实 | 只给商品有符号记录金额，不称净收入 | 没有支付退款流水，候选匹配不作真值 | 质量与报告口径 |
| v1.0 / S01 | 原计划把Tableau纳入首版 | 按用户明确要求本次完成第1-10节，第11节延后 | 分析交付单独验收，不假称看板完成 | 计划与验收状态 |

新变更需记录原因、影响和复验；不得为通过检查修改容差掩盖错误。
''')
c.close();print('Wrote analysis documentation',flush=True)
