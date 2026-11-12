from PIL import Image,ImageDraw,ImageFont
import csv
from collections import defaultdict
from decimal import Decimal
font='/System/Library/Fonts/Hiragino Sans GB.ttc'
names={}; months=defaultdict(Decimal); products=defaultdict(Decimal); types=defaultdict(Decimal)
with open('data/exports/sales_lines.csv') as f:
 for r in csv.DictReader(f):
  if '2009-12-01'<=r['Month']<='2011-11-01':
   names[r['StockCode']]=r['Description'].strip(); a=Decimal(r['LineAmount']); months[r['Month']]+=a; products[r['StockCode']]+=a; types[r['CustomerType']]+=a
for soft,name in [(True,'tableau-portfolio-refined')]:
 im=Image.new('RGB',(1600,1100),'#EDEFEA' if soft else '#FFFFFF'); d=ImageDraw.Draw(im)
 ink='#1E302D'; muted='#64756D'; line='#DCE2DB'; accent='#28765B' if soft else '#28765B'
 def txt(x,y,t,size=18,color=ink):
  chosen='/System/Library/Fonts/Supplemental/Arial Bold.ttf' if t.isascii() and size>=25 else ('/System/Library/Fonts/Supplemental/Arial.ttf' if t.isascii() else font)
  d.text((x,y),t,font=ImageFont.truetype(chosen,size),fill=color)
 def panel(box):
  d.rounded_rectangle(box,12,fill='#E5E9E1')
 d.rounded_rectangle((50,40,56,103),3,fill=accent)
 txt(73,35,'电商经营概览',32);txt(75,88,'销售表现与客户结构  /  UCI Online Retail II',16,muted)
 txt(1190,49,'2009.12 — 2011.11',21,muted)
 txt(50,142,'国家',16,muted);d.rounded_rectangle((110,130,430,174),6,outline='#BCC9BD',fill='#E5E9E1');txt(127,142,'全部国家',16);d.polygon([(400,149),(412,149),(406,156)],fill=muted)
 txt(480,142,'月份范围',16,muted);txt(580,142,'2009/12',16);d.line((680,153,1430,153),fill='#A3BCAF',width=4);d.ellipse((674,147,686,159),fill=accent);d.ellipse((1424,147,1436,159),fill=accent);txt(1450,142,'2011/11',16)
 metrics=[('商品正向交易金额','19.09M','GBP · 19,085,461.19'),('购买订单数','38,700','去重订单'),('已识别购买客户','5,824','范围内去重'),('客单价','493.16','GBP / 订单')]
 for x,w,(label,value,unit) in zip([50,510,865,1220],[435,330,330,330],metrics):
  panel((x,192,x+w,325));
  if x==50:d.rounded_rectangle((x,192,x+w,325),12,fill='#C4DEAE')
  if not soft:d.line((x,192,x+w,192),fill=line,width=2)
  txt(x+18,205,label,18,muted);txt(x+18,241,value,35);txt(x+18,292,unit,14,muted)
 panel((50,347,1550,650));txt(70,365,'月度交易金额',22);txt(300,371,'GBP',15,muted)
 x0,x1,y0,y1=145,1505,415,594
 for val in [0,500000,1000000,1500000]:
  y=y1-val/1600000*(y1-y0);d.line((x0,y,x1,y),fill=line,width=1);txt(70,y-9,f'{val/1000000:g}M',14,muted)
 vals=[float(months[k]) for k in sorted(months)];pts=[(x0+i*(x1-x0)/23,y1-v/1600000*(y1-y0)) for i,v in enumerate(vals)]
 for i,(px,py) in enumerate(pts):
  d.rounded_rectangle((px-13,py,px+13,y1),3,fill=accent if vals[i]==max(vals) else '#A3BCAF')
 peak=vals.index(max(vals)); txt(pts[peak][0]-150,pts[peak][1]-28,f'最高月份  {max(vals)/1e6:.2f}M GBP',16,accent)
 for i,label in [(0,'2009/12'),(6,'2010/06'),(12,'2010/12'),(18,'2011/06'),(23,'2011/11')]:txt(pts[i][0]-30,610,label,14,muted)
 panel((50,672,870,979));panel((890,672,1550,979));txt(70,691,'商品交易金额 Top10',22);txt(910,691,'新老客交易金额构成',22)
 top=sorted(products.items(),key=lambda a:a[1],reverse=True)[:10];maxv=float(top[0][1])
 for i,(code,v) in enumerate(top):
  y=735+i*20
  label=names[code]
  label=label[:25]+'…' if len(label)>26 else label
  txt(72,y-2,label,12,muted)
  end=310+float(v)/maxv*410
  d.rectangle((310,y,end,y+12),fill=accent if i==0 else '#92B49E')
  txt(end+10,y-2,f'{float(v)/1000:.1f}K',13,ink)
 txt(590,947,'交易金额（GBP）',14,muted)
 ts=[('Existing','老客月份交易'),('New','首次观测月交易'),('Unknown','客户ID未知')]
 maxc=max(float(v) for v in types.values())
 for i,(key,label) in enumerate(ts):
  y=740+i*65; v=float(types.get(key,0)); total=float(sum(types.values()))
  txt(910,y,label,15,muted)
  txt(1270,y,f'{v/1e6:.2f}M | {v/total:.1%}',16,ink)
  d.rectangle((910,y+27,910+v/maxc*590,y+44),fill=[accent,'#A4C58E','#B4BEC8'][i])
 txt(1310,947,'交易金额（GBP）',14,muted)
 d.line((50,1002,1550,1002),fill=line,width=1)
 txt(50,1016,'口径：有效商品正向交易，不等同于扣除退货后的净销售额；订单与已识别客户按筛选范围去重。',15,muted)
 txt(50,1043,'新老客按首次观测购买月份划分。数据：2009年12月—2011年11月  |  美化方案预览，非 Tableau 截图',14,muted)
 im.save('outputs/'+name+'.png')
