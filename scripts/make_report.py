"""Generate a cover, contents and six-page analytical report and source-linked figures from computed exports."""
from pathlib import Path
import json,os,math
import pandas as pd,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
from matplotlib.ticker import PercentFormatter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,white
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
ROOT=Path(__file__).resolve().parents[1];E=ROOT/'data/exports';F=ROOT/'reports/figures';F.mkdir(parents=True,exist_ok=True)
FONT=os.environ.get('RETAIL_CJK_FONT','/System/Library/Fonts/Supplemental/Songti.ttc')
if not Path(FONT).exists():raise RuntimeError('Set RETAIL_CJK_FONT to a Chinese TrueType font (.ttf or compatible .ttc).')
fontManager.addfont(FONT);fp=FontProperties(fname=FONT)
plt.rcParams.update({'font.family':fp.get_name(),'font.size':11,'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#24384B','text.color':'#24384B','axes.titleweight':'bold','figure.facecolor':'white','savefig.facecolor':'white'})
BLUE='#214E70';TEAL='#087F8C';RED='#B84A48';GRAY='#718096';ORANGE='#B7791F'
S=json.loads((E/'analysis_summary.json').read_text());b=S['base'];n=S['current'];overview=S['overview_complete_period']
# Narrative is tied to this verified v1 study; fail rather than silently reusing it with changed periods.
assert S['config']['base_month']=='2010-11-01' and S['config']['current_month']=='2011-11-01'
assert abs(b['amount']-1435680.122)<1e-6 and abs(n['amount']-1457745.53)<1e-6
m=pd.read_csv(E/'metric_month.csv',parse_dates=['month']);m=m[m.complete_month]
q=pd.read_csv(E/'quality_summary.csv');cov=pd.read_csv(E/'quality_month.csv',parse_dates=['month']);cov=cov[cov.month<'2011-12-01']
factors=pd.read_csv(E/'factor_contributions.csv');g=pd.read_csv(E/'group_contributions.csv');co=pd.read_csv(E/'cohort_cells.csv',parse_dates=['first_month']);sens=pd.read_csv(E/'sensitivity.csv');comparison=pd.read_csv(E/'cohort_comparison.csv')

def save(fig,name):
 fig.savefig(F/f'{name}.png',dpi=180,bbox_inches='tight');plt.close(fig)

def tidy(ax):ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig,axs=plt.subplots(3,1,figsize=(10.6,5.6),sharex=True,layout='constrained')
for ax,col,label in zip(axs,['amount','orders','customers'],['商品正向金额（万GBP）','购买订单数','已识别购买客户数']):
 vals=m[col]/10000 if col=='amount' else m[col]
 ax.plot(m.month,vals,color=BLUE,marker='o',ms=3);ax.set_ylabel(label);tidy(ax)
 for date in ['2010-11-01','2011-11-01']:ax.axvline(pd.Timestamp(date),color=ORANGE,ls='--',lw=.8)
axs[-1].set_xlabel('交易月份（2009-12至2011-11，排除不完整尾月）');save(fig,'01_monthly_trend')
fig,ax=plt.subplots(figsize=(10.6,3.0),layout='constrained');ax.plot(m.month,m.identified_amount_coverage,color=TEAL,marker='o',ms=3);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.set_ylim(.65,1);ax.set_ylabel('已识别客户金额 / 全量商品正向金额');tidy(ax);ax.set_xlabel('交易月份');save(fig,'02_coverage')
fig,ax=plt.subplots(figsize=(10.6,3.4),layout='constrained')
values=[b['known_amount']/10000,*list(factors.contribution/10000),n['known_amount']/10000]
starts=[0,values[0],values[0]+values[1],values[0]+values[1]+values[2],0]
labels=['2010-11金额','人数贡献','频次贡献','客单价贡献','2011-11金额']
for i,(v,start) in enumerate(zip(values,starts)):
 color=BLUE if i in(0,4) else TEAL if v>0 else RED
 ax.bar(i,abs(v),bottom=min(start,start+v) if i not in(0,4) else 0,color=color,width=.65)
 ax.text(i,max(start,start+v)+2, f'{v:+.2f}' if i not in(0,4) else f'{v:.2f}',ha='center',fontsize=11)
ax.set_xticks(range(5),labels);ax.set_ylabel('万GBP，已识别客户正向金额');ax.set_ylim(0,132);tidy(ax);save(fig,'03_factor_waterfall')
product_names=pd.read_csv(E/'product_month.csv',dtype={'stock_code':str}).drop_duplicates('stock_code',keep='last').set_index('stock_code')['description'].to_dict()
fig,axs=plt.subplots(1,2,figsize=(12.8,6.8),layout='constrained')
for ax,dim,title in zip(axs,['product','country'],['商品贡献（编码及名称节选）','国家贡献']):
 d=g[g.dimension==dim].head(7).copy();rest=g[g.dimension==dim].contribution.sum()-d.contribution.sum()
 names=list(d.group_name.astype(str))+['其他']
 if dim=='product':names=[x+'\n'+str(product_names.get(x,''))[:22] if x!='其他' else x for x in names]
 vals=list(d.contribution/10000)+[rest/10000]
 names=[{'United Kingdom':'英国','France':'法国','Australia':'澳大利亚','Netherlands':'荷兰','Japan':'日本','Switzerland':'瑞士','Germany':'德国'}.get(x,x) for x in names]
 y=np.arange(len(names));ax.barh(y,vals,color=[TEAL if x>=0 else RED for x in vals]);ax.set_yticks(y,names);ax.invert_yaxis();ax.axvline(0,color=GRAY,lw=.8)
 for i,v in enumerate(vals):ax.text(v+(.06 if v>=0 else -.06),i,f'{v:+.2f}',va='center',ha='left' if v>=0 else 'right',fontsize=10)
 ax.set_xlim(min(vals)-.9,max(vals)+1.0);ax.set_title(title);ax.set_xlabel('2011-11同比贡献（万GBP）');ax.grid(axis='x',alpha=.15)
save(fig,'04_group_contributions')
heat=co[(co.first_month<'2011-12-01')&(co.month_age.between(1,12))].pivot(index='first_month',columns='month_age',values='repurchase_rate')
fig,ax=plt.subplots(figsize=(10.6,6.4),layout='constrained');cmap=plt.get_cmap('YlGnBu').copy();cmap.set_bad('#E2E8F0')
im=ax.imshow(heat.values,aspect='auto',cmap=cmap,vmin=0,vmax=.5)
ax.set_yticks(range(len(heat)),[f'{x:%Y-%m}' for x in heat.index]);ax.set_xticks(range(12),range(1,13));ax.set_xlabel('首次观测购买后的第k个自然月（非累计）');ax.set_ylabel('首次观测购买月份')
for i in range(len(heat)):
 for j in range(12):
  v=heat.iloc[i,j]
  if not pd.isna(v):ax.text(j,i,f'{v:.0%}',ha='center',va='center',fontsize=7.8,color='white' if v>.31 else '#24384B')
fig.colorbar(im,ax=ax,fraction=.025,pad=.02,format=PercentFormatter(1),label='回购人数 / 原队列人数');save(fig,'05_cohort_heatmap')
fig,ax=plt.subplots(figsize=(10.6,3.0),layout='constrained');ss=sens.iloc[:4]
labels=['主口径：保留大额订单','仅去除表内重复','排除最高约1%订单','表内去重＋排除大额']
ax.barh(labels,ss.growth*100,color=[TEAL if x>=0 else RED for x in ss.growth]);ax.invert_yaxis();ax.axvline(0,color=GRAY,lw=.8)
for i,v in enumerate(ss.growth*100):ax.text(v+(.08 if v>=0 else -.08),i,f'{v:+.2f}%',ha='left' if v>=0 else 'right',va='center')
ax.set_xlim(-4.7,2.6);ax.set_xlabel('2011年11月商品正向金额同比');ax.grid(axis='x',alpha=.15);save(fig,'06_sensitivity')
# Product-only exhibit for the narrative page.
d=g[g.dimension=='product'].head(7).copy()
vals=list(d.contribution/10000)+[(g[g.dimension=='product'].contribution.sum()-d.contribution.sum())/10000]
names=[str(x)+'  '+str(product_names.get(str(x),''))[:25] for x in d.group_name]+['其他商品']
fig,ax=plt.subplots(figsize=(10.8,4.0),layout='constrained')
ax.barh(range(len(vals)),vals,color=[TEAL if v>=0 else RED for v in vals]);ax.set_yticks(range(len(vals)),names);ax.invert_yaxis();ax.axvline(0,color=GRAY,lw=.8)
for i,v in enumerate(vals):ax.text(v+(.06 if v>=0 else -.06),i,f'{v:+.2f}',va='center',ha='left' if v>=0 else 'right',fontsize=11)
ax.set_xlim(min(vals)-.8,max(vals)+.8);ax.set_xlabel('交易金额同比变化（万GBP）');ax.grid(axis='x',alpha=.12)
save(fig,'07_product_contributions')
# PDF layout. Body positions are checked to prevent unnoticed overflow.
pdfmetrics.registerFont(TTFont('CN',FONT))
REPORT=ROOT/'reports/电商销售波动与复购分析报告.pdf';c=canvas.Canvas(str(REPORT),pagesize=(595.28,841.89));c.setTitle('电商销售波动与用户复购分析');c.setAuthor('公开数据个人项目')
style=ParagraphStyle('body',fontName='CN',fontSize=11.5,leading=17,textColor=HexColor('#24384B'),spaceAfter=7)
small=ParagraphStyle('small',parent=style,fontSize=9.5,leading=13)
y=0;page=0

def begin(title,kicker):
 global y,page
 page+=1;c.bookmarkPage(f'section_{page}');c.addOutlineEntry(title,f'section_{page}',level=0);c.setFillColor(HexColor(BLUE));c.rect(0,813,595.28,29,fill=1,stroke=0)
 c.setFillColor(white);c.setFont('CN',9);c.drawString(42,823,'公开数据个人项目  /  UCI ONLINE RETAIL II')
 c.setFillColor(HexColor(BLUE));c.setFont('CN',23);c.drawString(42,773,title)
 c.setFont('CN',10);c.setFillColor(HexColor(GRAY));c.drawString(42,751,kicker)
 c.setStrokeColor(HexColor('#CBD5E0'));c.line(42,738,553,738);y=722

def para(text,small_text=False):
 global y
 p=Paragraph(text,small if small_text else style);w,h=p.wrap(511,y-65);assert y-h>65,(page,text,y,h)
 p.drawOn(c,42,y-h);y-=h+8

def heading(text):
 global y
 c.setFont('CN',13);c.setFillColor(HexColor(BLUE));c.drawString(42,y-14,text);y-=26

def picture(name,height):
 global y
 path=F/f'{name}.png';img=ImageReader(str(path));iw,ih=img.getSize();w=min(511,height*iw/ih);h=w*ih/iw
 assert y-h>62,(page,name,y,h);c.drawImage(img,42+(511-w)/2,y-h,width=w,height=h);y-=h+8

def table(headers,rows,widths=None):
 global y
 cells=[[Paragraph(str(v),small) for v in row] for row in [headers]+rows]
 t=Table(cells,colWidths=widths or [511/len(headers)]*len(headers),hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#E9F0F5')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.6,HexColor(BLUE)),('LINEBELOW',(0,1),(-1,-1),.25,HexColor('#DCE3E9'))]))
 w,h=t.wrap(511,y-60);assert y-h>60,(page,'table',y,h);t.drawOn(c,42,y-h);y-=h+12

def end():
 c.setStrokeColor(HexColor('#CBD5E0'));c.line(42,48,553,48);c.setFillColor(HexColor(GRAY));c.setFont('CN',8)
 c.drawString(42,33,'来源：Chen (2012), UCI Online Retail II, DOI: 10.24432/C5CG6D · CC BY 4.0')
 c.drawRightString(553,33,f'{page+2} / 8');c.showPage()

# Unnumbered cover; body retains its six-page numbering and traceability references.
c.setFillColor(HexColor('#F3F6F8'));c.rect(0,0,595.28,841.89,fill=1,stroke=0)
c.setFillColor(HexColor(BLUE));c.rect(0,0,19,841.89,fill=1,stroke=0)
c.setFont('CN',11);c.drawString(58,765,'公开数据个人分析作品')
c.setStrokeColor(HexColor(TEAL));c.setLineWidth(3);c.line(58,674,133,674)
c.setFont('CN',34);c.drawString(58,612,'电商销售波动')
c.drawString(58,562,'与用户复购分析')
c.setFont('CN',15);c.setFillColor(HexColor(GRAY));c.drawString(60,514,'UCI Online Retail II')
c.setFont('CN',13);c.setFillColor(HexColor(BLUE));c.drawString(60,449,'以2011年11月同比为重点，结合客户复购队列')
c.setStrokeColor(HexColor('#CFD9E1'));c.setLineWidth(.6);c.line(60,373,535,373)
for yy,label,value in [(338,'分析期间','2009年12月 - 2011年11月'),(303,'专题比较','2011年11月与2010年11月同比'),(268,'分析方法','SQL建模 / 销售贡献分解 / 复购队列'),(233,'报告日期',S['generated_at'][:10])]:
 c.setFillColor(HexColor(GRAY));c.setFont('CN',10);c.drawString(60,yy,label)
 c.setFillColor(HexColor(BLUE));c.setFont('CN',12);c.drawString(145,yy,value)
c.setFont('CN',9);c.setFillColor(HexColor(GRAY));c.drawString(60,104,'历史交易数据研究 · 描述性分析 · 数据与方法可追溯')
c.setFont('CN',8);c.drawString(60,78,'数据来源：Chen (2012), UCI Machine Learning Repository · CC BY 4.0')
c.showPage()

# Contents uses physical PDF page numbers, including cover and contents.
c.setFillColor(HexColor(BLUE));c.rect(0,813,595.28,29,fill=1,stroke=0)
c.setFillColor(white);c.setFont('CN',9);c.drawString(42,823,'公开数据个人项目  /  UCI ONLINE RETAIL II')
c.setFillColor(HexColor(BLUE));c.setFont('CN',28);c.drawString(42,770,'目录')
c.setFont('CN',10);c.setFillColor(HexColor(GRAY));c.drawString(42,744,'先读执行摘要，再按业务问题查看分析依据与行动方案')
c.setStrokeColor(HexColor('#CBD5E0'));c.line(42,729,553,729)
contents=[
 ('01','执行摘要：问题、结论与行动','业务目标、核心结论与建议行动',3),
 ('02','销售变化分析','增长判断（第4页）与因素拆解（第5页）',4),
 ('03','商品与客群贡献','定位推动与拖累销售的商品和客群',6),
 ('04','客户复购分析','同月龄队列与次月复购表现',7),
 ('05','业务行动方案','组合推荐、商品资源调整与客户跟进',8)]
for j,(number,title,desc,target) in enumerate(contents):
 yy=674-j*100
 c.setFillColor(HexColor(TEAL));c.setFont('CN',13);c.drawString(42,yy,number)
 c.setFillColor(HexColor(BLUE));c.setFont('CN',15);c.drawString(80,yy,title)
 c.drawRightString(550,yy,str(target))
 c.setFillColor(HexColor(GRAY));c.setFont('CN',10);c.drawString(80,yy-23,desc)
 c.setStrokeColor(HexColor('#E2E8F0'));c.line(80,yy-38,553,yy-38)
 c.linkRect('',f'section_{target-2}',(42,yy-30,553,yy+18),relative=0,thickness=0)
c.setFont('CN',9);c.drawString(42,100,'页码按PDF实际页面计算，包含封面与目录；点击目录可跳转。')
c.setStrokeColor(HexColor('#CBD5E0'));c.line(42,48,553,48)
c.setFont('CN',8);c.drawRightString(553,33,'2 / 8');c.showPage()

begin('执行摘要：问题、结论与行动','分析范围：2009-12至2011-11；销售专题：2011年11月同比')
heading('业务现状与分析目的')
para('2011年11月商品正向交易金额同比增长1.54%。本报告判断这次增长是否稳健，定位销售变化的主要因素，并识别客户持续购买的运营机会，为资源投入和试点选择提供依据。')
heading('三个问题、三个判断、三类行动')
table(['业务问题','核心结论','建议行动'],[
 ['1. 销售为什么变化，增长是否稳健？','排除大额订单后同比为-3.40%；已识别客户客单价下降4.38%，负向贡献超过人数增长的正向贡献。','优先试点互补推荐与组合购买；大额与普通订单分开评价。'],
 ['2. 哪些商品和客群值得关注？','商品涨跌并存；首次观测月客户贡献下降，已有历史客户贡献增加。','选择候选商品调整推荐；需求、库存和毛利支持后才调整备货。'],
 ['3. 客户是否持续购买？','同期队列次月复购率20.49%→23.60%，增加3.11个百分点；并非运营效果的因果证据。','试点首购后使用建议、相关推荐与回购提醒，用对照组验证。']],[126,205,180])
heading('建议决策：先小范围试点，再决定扩大')
para('优先验证订单价值方案；商品资源与客户触达按条件成熟度推进。试点前确认预算、样本量和停止条件，以增量毛利及转化、退货或退订约束共同判断效果。具体措施与协作角色见第8页。')
heading('如何阅读本报告')
para('第4—5页回答问题1：先判断增长稳定性，再拆解金额变化；第6页回答问题2：定位商品与客群差异；第7页回答问题3：比较客户后续购买。每页按结论、证据、业务解释和行动启示展开。')
para('范围：2009年12月至2011年11月；销售专题为两期11月同比。金额为GBP有效商品正向交易，未扣除退货，不是净收入或利润。全部业务方案尚未实施。',True)
end()

begin('问题1：销售为什么变化，增长是否稳健？','问题1 · 第一步：比较2011年11月与2010年11月的交易表现')
heading('结论：增长对大额订单敏感，不能认定普遍改善')
para('全量商品正向金额同比增长1.54%；使用同一门槛排除大额订单后，同比下降3.40%。这说明增长方向受大额订单影响，但不意味着大额订单无效。')
heading('证据1：去重影响小，排除大额订单影响大')
picture('06_sensitivity',185)
para(f"读图：蓝绿色为同比增长，红色为下降。仅去除表内重复，增长率为1.57%，与主口径接近。大额门槛为完整分析期订单金额99分位数{S['extreme_order_threshold']:,.4f} GBP，两期统一按此门槛整单排除；主分析仍保留大额交易。",True)
heading('业务解释：总额增长不能替代分层经营判断')
para('大额交易可能来自真实批发需求，应保留其经营价值；但总额会掩盖其他订单的表现。因此应同时跟踪大额与普通订单的金额、订单数和持续购买情况，不能仅以整体+1.54%判断全面改善。')
heading('行动启示：分层跟踪，维护可识别的大额客户')
para('为可识别的大额客户提供补货提醒和订单服务；普通订单的增长另行评价。这是对订单集中度敏感的管理应对，不代表已经证明客户流失或服务不足。')
heading('分析范围衔接：下一页为什么看已识别客户？')
para('客户ID非空的金额同比下降1.70%（减少19,708.64 GBP），客户ID未知金额增加41,774.05 GBP，合计增加22,065.41 GBP。只有已识别客户能按人数、频次和客单价拆解，因此下一页限定在该范围。',True)
para('已识别金额覆盖率80.93%→78.35%，会影响客户分析代表性。ID未知不代表订单无效；大额订单与ID未知是两种分类，不能认为是同一批订单。',True)
end()

begin('已识别客户金额为何下降？','问题1 · 第二步：仅分析客户ID非空的交易，两期口径一致')
heading('结论：客单价下降的拖累超过人数增长的贡献')
para('已识别客户金额减少19,708.64 GBP（-1.70%）。购买人数增加，但客单价和人均订单数下降，合计抵消了人数增长。')
heading('拆解逻辑：金额 = 人数 × 人均订单数 × 客单价')
table(['指标','2010年11月','2011年11月','变化方向'],[
 ['购买客户数','1,606','1,660','上升3.36%'],['人均订单数','1.6002','1.5916','小幅下降'],['客单价（GBP/订单）','452.08','432.30','下降4.38%']],[151,120,120,120])
heading('关键证据：三个因素分别贡献多少金额变化？')
picture('03_factor_waterfall',190)
para('读图：两端蓝柱是两期金额；中间是因素贡献。人数增加贡献+38,108.57 GBP，频次下降贡献-6,269.09 GBP，客单价下降贡献-51,548.12 GBP，三项合计为-19,708.64 GBP。')
para('方法说明：贡献采用Shapley分解，平均三因素全部6种替换顺序。它量化指标变化的贡献，不证明降价、缺货或促销是业务原因。',True)
heading('业务解释：人数增加未能抵消每单金额下降')
para('在已识别客户范围内，仅扩大购买人数不足以抵消本期负向变化，应同时关注每笔订单的购买价值。分解尚不能确定是价格、每单件数还是商品组合导致客单价下降。')
heading('行动启示：优先验证订单价值方案')
para('小范围测试互补推荐与组合购买，目标是提高每单件数；同时评价转化率和每位分配用户的毛利，避免只提高客单价却损害总收益。下一页恢复全量口径，定位商品与客群差异。')
end()

begin('哪些商品和客群推动或拖累销售？','问题2 · 全量交易口径：各维度分别解释同比增加的22,065.41 GBP')
heading('结论：增长来源分化，资源应有选择地投入')
para('总额微增掩盖了内部差异。商品资源与客户运营应分别选择重点，不能对所有商品和客群采用相同措施。')
heading('商品：定位重点推荐与调整候选')
picture('07_product_contributions',190)
para('23084（兔子夜灯）增加34,556.72 GBP；84347和22423分别减少16,077.40和14,351.75 GBP。这些是贡献变化而非销售规模排名，适合筛选调查与试点候选；不能仅凭贡献方向决定采购或折扣。',True)
heading('客群：区分首购表现与老客经营')
table(['客户类别','同比金额贡献（GBP）','含义'],[
 ['首次观测购买月客户','-72,586.54','该类别交易金额下降'],['已有更早购买记录的客户','+52,877.90','该类别交易金额增加'],['客户ID未知','+41,774.05','无法归入前两类']],[215,135,161])
para('首次观测月客户贡献下降，不能直接判定获客失败；历史客户贡献增加，也不等于复购率提高。分类会受观测历史累积影响，需要把首购后的持续购买单独分析。')
heading('业务解释与行动启示：商品、客户分别配置资源')
para('对增长商品，先结合近期需求、库存和毛利评估推荐及补货；对下降商品，小范围验证搭配推荐，避免统一打折。客群金额只能定位变化，不能判断复购好坏；下一页用同月龄比较后续购买，再设计首购跟进。')
para('口径：贡献=本期金额-基期金额；商品图取绝对贡献前7项并补“其他”。商品与客群是同一变化的两个切面，不能相加；首次观测购买不等于真实首购，基期无交易不等于新品上市。',True)
end()

begin('客户后续购买表现如何？','问题3 · 已识别客户：比较2010年与2011年1—10月首次观测队列')
heading('结论：次月复购率增加3.11个百分点')
para('2011年同期队列的合并次月复购率为23.60%，高于2010年的20.49%。这是观察到的队列差异，不证明某项运营措施有效。')
heading('比较规则与主要证据')
para('将首次观测购买月份相同的客户分为一组，观察他们在下一自然月是否再次购买。只纳入次月已完整观察的队列，合并比例按队列人数加权。',True)
table(['队列年份（1—10月）','客户人数','次月回购人数','次月复购率'],[[str(int(r.cohort_year)),f'{int(r.cohort_customers):,}',f'{int(r.returning_customers):,}',f'{r.month1_rate:.2%}'] for r in comparison.itertuples()],[175,100,120,116])
heading('辅助证据：不同队列后续各月的回购情况')
para('读图：每行是一组客户，每列是首次观测后的第k个自然月；格子表示原队列中该月回来购买的比例。向右看同组客户后续表现，沿同一列比较相同月龄。灰色表示未完整观察，不是零回购。',True)
picture('05_cohort_heatmap',245)
heading('业务解释与行动启示：提升机会，不是恶化补救')
para('数据未证明复购恶化，也不能证明已有运营措施有效。首购后跟进属于持续购买促进试点：提供使用建议、相关推荐与回购提醒，保留随机对照组，以30天回购及增量毛利决定是否扩大。具体执行见下一页。')
para('边界：首次观测不等于真实首购；2009年12月尤其混入历史老客，后续队列受历史累积和客群结构影响。自然月次月复购与固定30天试验指标不同，不能直接替代。',True)
end()

begin('业务行动：按优先级开展试点','建议方案，尚未实施；优先级依据问题直接性与实施条件，不代表预计收益排名')
heading('行动对象与执行方式')
table(['优先级／目标','具体业务动作与对象','配合角色与试点方式'],[
 ['P1 提高普通订单价值','面向普通订单客户，在详情页或购物车增加互补商品推荐与组合购买入口；首轮不默认降价。','商品运营＋产品／技术＋数据分析；选择少量有库存、可核算毛利的商品，按客户或会话随机分组。'],
 ['P2 有选择地配置商品资源','将增长与下降贡献商品列为候选，测试推荐位置和搭配；仅在近期需求、库存及毛利支持后调整补货。','商品运营＋供应链＋数据分析；推荐随机对照，补货分批实施并监测库存风险。'],
 ['P3 促进首购后再次购买','面向可识别且允许触达的客户，提供使用建议、相关推荐与适时回购提醒；对已有高频记录客户提供补货提醒。','客户运营＋数据分析；使用实施前信息确定名单，随机保留对照组，先验证基础触达。']],[100,225,186])
heading('怎样判断扩大、调整或停止？')
table(['方案','主要效果指标','约束与决策规则'],[
 ['P1 组合推荐','每单件数、客单价；每位分配用户的毛利增量','同时看转化与退货；不能仅凭客单价上升判成功。'],
 ['P2 商品资源','品类整体毛利与销售；缺货、周转和积压','检查是否挤占其他商品销售；补货前后变化不直接视为因果效果。'],
 ['P3 首购跟进','固定30天回购；每位分配客户的毛利增量','监测退订、退货和触达成本；与随机对照比较，不直接套用自然月复购率。']],[100,205,206])
heading('启动前确认与共同行动')
para('各试点启动前确认预算、样本量、效果门槛和停止条件，按预先约定标准决定是否扩大；当前数据不足以给出可信的收益预测或统一门槛。大额订单单独跟踪，并为可识别客户提供订单服务。')
para('老客维护依据：全期累计购买10次及以上的941位客户贡献已识别金额约66.9%，仅为事后集中度描述；不可直接将全期名单用于模拟历史触达。缺少成本、库存和支付退款等资料，须补齐相应实施条件。',True)
end()

c.save();assert page==6
# Text companion for search, editing and evidence links.
md=f'''# 电商销售波动与用户复购分析报告

处理日期：{S['generated_at'][:10]}。公开历史数据个人项目；分析第1-10节已完成；Tableau经营看板已制作并展示，在线发布尚未确认，第11节不整体标记完成。

专题：以2011年11月对2010年11月同比为重点，结合客户复购队列。

## 目录

以下页码为配套PDF实际页码，包含封面与目录。

| 章节 | PDF页码 |
| --- | ---: |
| 1. 执行摘要：问题、结论与行动 | 3 |
| 2. 销售变化分析 | 4–5 |
| 3. 商品与客群贡献 | 6 |
| 4. 客户复购分析 | 7 |
| 5. 业务行动方案 | 8 |

## 1. 执行摘要：问题、结论与行动

**现状与目标：**2011年11月商品正向交易金额同比增长1.54%。判断增长是否稳健，定位销售变化的主要因素，并识别持续购买的运营机会，为资源投入和试点选择提供依据。

| 业务问题 | 核心结论 | 建议行动 |
| --- | --- | --- |
| 销售为什么变化，增长是否稳健？ | 排除大额订单后同比-3.40%；已识别客户客单价下降4.38%，负向贡献超过人数增长的正向贡献 | P1：互补推荐与组合购买；大额和普通订单分开评价 |
| 哪些商品和客群值得关注？ | 商品涨跌并存；首次观测月客户贡献下降、历史客户贡献增加 | P2：选择候选商品调整推荐；需求、库存与毛利支持后才调整备货 |
| 客户是否持续购买？ | 次月复购率20.49%→23.60%，增加3.11个百分点，非运营效果的因果证据 | P3：首购后使用建议、相关推荐及回购提醒，以对照组验证 |

**建议决策：**优先验证订单价值方案，其余按条件成熟度推进。试点前确认预算、样本量和停止条件，以增量毛利及转化、退货或退订约束共同判断效果。业务方案尚未实施。

**阅读路径：**第4—5页判断增长与拆解因素；第6页定位商品和客群；第7页比较复购；第8页给出业务行动。金额为GBP商品正向交易金额，未扣除退货，不是净收入或利润。

## 2. 销售变化分析

### 2.1 问题1：销售为什么变化，增长是否稳健？

**结论：**全量商品正向金额同比增长1.54%，但使用同一门槛排除大额订单后下降3.40%，不能认定普遍改善。

**证据1：增长对大额订单敏感，去重影响较小。**

![不同处理方式下的同比变化](figures/06_sensitivity.png)

仅去除表内重复，同比为+1.57%。大额门槛为完整分析期订单金额99分位数4,008.5903 GBP，两期用同一门槛整单排除；主分析仍保留真实大额交易。

**业务解释：**大额交易可能来自真实批发需求，应保留其经营价值；总额同时可能掩盖其他订单的表现，因此应分开跟踪金额、订单数和持续购买，不能仅凭+1.54%认定全面改善。

**行动启示：**维护可识别的大额客户，提供补货提醒与订单服务；普通订单另行评价。这不是已经证明客户流失或服务不足。

**下一页的分析范围：**已识别客户金额下降1.70%（减少19,708.64 GBP），未知客户金额增加41,774.05 GBP，合计增加22,065.41 GBP。只有已识别客户能做人数、频次及客单价拆解。已识别金额覆盖率80.93%→78.35%，影响代表性；未知ID不代表无效订单，也不等于大额订单。

### 2.2 已识别客户金额为何下降？

**结论：**客单价下降的负向贡献超过人数增长的正向贡献，已识别客户金额减少19,708.64 GBP（-1.70%）。

**拆解逻辑：交易金额 = 购买人数 × 人均订单数 × 客单价。**仅对客户ID非空交易计算。

| 指标 | 2010年11月 | 2011年11月 | 变化 |
| --- | ---: | ---: | --- |
| 购买人数 | 1,606 | 1,660 | +3.36% |
| 人均订单数 | 1.6002 | 1.5916 | 小幅下降 |
| 客单价（GBP/订单） | 452.08 | 432.30 | -4.38% |

![人数、频次和客单价的贡献](figures/03_factor_waterfall.png)

人数、频次、客单价分别贡献+38,108.57、-6,269.09、-51,548.12 GBP，合计-19,708.64 GBP。两端蓝柱为两期金额，中间为因素贡献。Shapley平均全部6种替换顺序，只解释数值变化，不识别业务原因。

**业务解释：**购买人数增加未抵消每单金额下降，应同时关注订单价值；尚不能确定原因是价格、件数还是商品组合。

**行动启示：**优先测试互补推荐与组合购买，目标是提高每单件数，同时评价转化及每位分配用户的毛利，避免客单价提高却损害总收益。**下一问：哪些商品和客群推动或拖累销售？**下面恢复全量交易口径，从另一个角度定位变化。

## 3. 哪些商品和客群推动或拖累销售？

**结论：**增长来源分化，资源应有选择地投入；商品和客户分别配置运营动作。

### 商品：定位推荐与调整候选

![商品同比金额贡献](figures/07_product_contributions.png)

23084（RABBIT NIGHT LIGHT，兔子夜灯）贡献+34,556.72 GBP；84347、22423分别贡献-16,077.40、-14,351.75 GBP。增长商品进入推荐与备货评估候选，下降商品可小范围测试搭配推荐；须结合近期需求、库存与毛利确认投入。

### 客群：区分首购表现与老客经营

| 客户类别 | 同比金额贡献（GBP） | 含义 |
| --- | ---: | --- |
| 首次观测购买月客户 | -72,586.54 | 该类别交易金额下降 |
| 已有更早购买记录的客户 | +52,877.90 | 该类别交易金额增加 |
| 客户ID未知 | +41,774.05 | 无法归入前两类 |

首次观测月客户贡献下降不等于获客失败；历史客户金额增加不等于复购率提高。分类受历史累积影响。

**业务含义：**商品分层配置推荐与补货资源，客户分别安排首购后跟进与老客维护。**下一问：客户是否持续回来购买？**

贡献为本期金额减基期金额。商品图取绝对贡献前7项，加“其他”闭合；商品和客群各自解释全量增加22,065.41 GBP，不能跨维度相加。首次观测不等于真实首购，基期无交易不等于新品上市。

## 4. 客户后续购买表现如何？

**结论：**同期队列次月复购率20.49%→23.60%，增加3.11个百分点；是描述性差异，不能归因于运营策略。

### 比较规则与主要证据

同一首次观测购买月的客户组成队列，统计下一自然月再次购买的人数。只比较完整观察的次月，合并比例按队列人数加权。

| 队列范围 | 客户人数 | 次月回购人数 | 次月复购率 |
| --- | ---: | ---: | ---: |
| 2010年1—10月 | 2,962 | 607 | 20.49% |
| 2011年1—10月 | 1,318 | 311 | 23.60% |

### 辅助证据：后续各月的回购情况

读图：每行是首次观测购买月，每列是此后第k个自然月，格子为原队列在该月回购的比例。横向看同组客户后续表现，纵向比较相同月龄；灰色是未完整观察，不是零。

![复购队列](figures/05_cohort_heatmap.png)

**业务解释：**数据未证明复购恶化，也不证明既有运营有效。

**行动启示：**首购后使用建议、相关推荐和回购提醒属于持续购买促进试点，而不是恶化补救；以随机对照验证30天回购及增量毛利。下一节汇总业务行动。

首次观测不等于真实首购；2009年12月尤其混入历史老客，后续队列受历史累积与客群结构影响。自然月次月复购不等于固定30天回购，不将月龄0视为复购。

## 5. 业务行动方案（建议试点，尚未实施）

优先级依据问题直接性和实施条件，不代表预计收益排名。

| 优先级／目标 | 对象与具体动作 | 协作和试点 | 评价与决策 |
| --- | --- | --- | --- |
| P1 提高普通订单价值 | 普通订单客户；详情页或购物车增加互补推荐、组合购买入口，首轮不默认降价 | 商品运营、产品／技术、数据分析；少量库存和毛利条件具备商品，客户或会话随机分组 | 件数、客单价、每位分配用户毛利增量；转化及退货约束达标后再扩大 |
| P2 配置商品资源 | 贡献增长和下降商品作为候选，测试推荐位置和搭配；需求、库存与毛利支持后调整补货 | 商品运营、供应链、数据分析；推荐随机对照，补货分批实施 | 品类整体销售毛利、缺货和库存周转；排查销售转移与积压，简单前后变化不视为因果效果 |
| P3 促进首购后购买 | 可识别且允许触达客户；使用建议、相关推荐和回购提醒；高频客户提供补货提醒 | 客户运营、数据分析；按实施前信息确定名单，随机保留对照组 | 30天回购、每位分配客户毛利增量；监测退订、退货和触达成本 |

**启动前确认：**预算、样本量、效果门槛和停止条件预先确定，按约定决定扩大、调整或停止。现有数据不支持可信的收益预测或统一门槛。大额订单单独跟踪，并为可识别客户提供订单服务。

**老客维护依据：**全期累计购买10次及以上的941位客户贡献已识别金额约66.9%，仅为事后集中度描述，不能用全期名单模拟历史触达。自然月次月复购与试验固定30天回购不直接替代。缺少成本、库存和支付退款等资料，须补齐相应实施条件。

来源：Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D. 许可CC BY 4.0。
'''
(ROOT/'reports/电商销售波动与复购分析报告.md').write_text(md)
print('Created',REPORT,flush=True)
if __name__=='__main__':pass
