from PIL import Image,ImageDraw,ImageFont
import csv
from collections import defaultdict
from decimal import Decimal
font='/System/Library/Fonts/Hiragino Sans GB.ttc'
months=defaultdict(Decimal); products=defaultdict(Decimal); types=defaultdict(Decimal)
with open('data/exports/sales_lines.csv') as f:
 for r in csv.DictReader(f):
  if '2009-12-01'<=r['Month']<='2011-11-01':
   a=Decimal(r['LineAmount']); months[r['Month']]+=a; products[r['StockCode']]+=a; types[r['CustomerType']]+=a
for soft,name in [(True,'tableau-flat-green')]:
 im=Image.new('RGB',(1600,1100),'#F0F4F7' if soft else '#FFFFFF'); d=ImageDraw.Draw(im)
 ink='#243447'; muted='#617487'; line='#E4EBF1'; accent='#258B88' if soft else '#397EAC'
 def txt(x,y,t,size=18,color=ink): d.text((x,y),t,font=ImageFont.truetype(font,size),fill=color)
 def panel(box):
  pass
 txt(50,35,'电商经营概览',36);txt(52,88,'公开数据个人项目  /  UCI Online Retail II',16,muted)
 txt(50,133,'国家',17,muted);d.rectangle((110,126,340,165),outline='#CBD7DF',fill='#F0F4F7');txt(125,135,'全部国家',17)
 txt(390,133,'月份范围',17,muted);d.rectangle((490,126,855,165),outline='#CBD7DF',fill='#F0F4F7');txt(505,135,'2009/12 — 2011/11',17)
 metrics=[('商品正向交易金额','19,085,461.19','GBP'),('购买订单数','38,700','去重订单'),('已识别购买客户','5,824','范围内去重'),('客单价','493.16','GBP / 订单')]
 for x,w,(label,value,unit) in zip([50,510,865,1220],[435,330,330,330],metrics):
  panel((x,192,x+w,325));
  if not soft:d.line((x,192,x+w,192),fill=line,width=2)
  txt(x+18,205,label,18,muted);txt(x+18,241,value,35);txt(x+18,292,unit,14,muted)
 panel((50,347,1550,650));txt(70,365,'月度交易金额趋势',22);txt(300,371,'GBP',15,muted)
 x0,x1,y0,y1=145,1505,415,594
 for val in [0,500000,1000000,1500000]:
  y=y1-val/1600000*(y1-y0);d.line((x0,y,x1,y),fill=line,width=1);txt(70,y-9,f'{val/1000000:g}M',14,muted)
 vals=[float(months[k]) for k in sorted(months)];pts=[(x0+i*(x1-x0)/23,y1-v/1600000*(y1-y0)) for i,v in enumerate(vals)]
 d.line(pts,fill=accent,width=4)
 for i,label in [(0,'2009/12'),(11,'2010/11'),(23,'2011/11')]:txt(pts[i][0]-30,610,label,14,muted)
 panel((50,672,870,979));panel((890,672,1550,979));txt(70,691,'商品交易金额 Top10',22);txt(910,691,'新老客交易金额构成',22)
 top=sorted(products.items(),key=lambda a:a[1],reverse=True)[:10];maxv=float(top[0][1])
 for i,(code,v) in enumerate(top):
  y=735+i*20;txt(72,y-2,code,14,muted);d.rectangle((155,y,155+float(v)/maxv*575,y+12),fill=accent if i==0 else ('#7AB9B5' if soft else '#8AB1CD'))
 txt(590,947,'交易金额（GBP）',14,muted)
 ts=[('Existing','老客月份交易'),('New','首次观测月交易'),('Unknown','客户ID未知')]
 maxc=max(float(v) for v in types.values())
 for i,(key,label) in enumerate(ts):
  y=752+i*61;txt(910,y+3,label,15,muted);v=float(types.get(key,0));d.rectangle((1075,y,1075+v/maxc*430,y+27),fill=[accent,'#9CBFCB','#B4BEC8'][i])
 txt(1310,947,'交易金额（GBP）',14,muted)
 d.line((50,1002,1550,1002),fill=line,width=1)
 txt(50,1016,'口径：有效商品正向交易，不等同于扣除退货后的净销售额；订单与已识别客户按筛选范围去重。',15,muted)
 txt(50,1043,'新老客按首次观测购买月份划分。数据：2009年12月—2011年11月  |  美化方案预览，非 Tableau 截图',14,muted)
 im.save('outputs/'+name+'.png')
print(dict(types))
