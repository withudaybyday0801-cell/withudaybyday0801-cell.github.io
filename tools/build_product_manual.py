"""Build the public manual HTML from the Markdown source; print with Chromium."""
from pathlib import Path
from html import escape
import re
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'docs/baodongni-product-manual.md').read_text()
def inline(s):
 s=escape(s)
 s=re.sub(r'https://baodongni\.onrender\.com',r'<a href="https://baodongni.onrender.com">baodongni.onrender.com ↗</a>',s)
 return s

def block(text):
 out=[];lines=text.strip().splitlines();i=0
 while i<len(lines):
  line=lines[i].strip()
  if not line:i+=1;continue
  if line.startswith('|'):
   rows=[]
   while i<len(lines) and lines[i].strip().startswith('|'):
    cells=[x.strip() for x in lines[i].strip().strip('|').split('|')];i+=1
    if all(re.fullmatch(r'[:\-\s]+',x) for x in cells):continue
    tag='th' if not rows else 'td';rows.append('<tr>'+''.join(f'<{tag}>{inline(x)}</{tag}>' for x in cells)+'</tr>')
   out.append('<table>'+''.join(rows)+'</table>');continue
  if line.startswith('### '):out.append('<h3>'+inline(line[4:])+'</h3>')
  elif line.startswith('## '):out.append('<h2>'+inline(line[3:])+'</h2>')
  else:out.append('<p>'+inline(line)+'</p>')
  i+=1
 return '\n'.join(out)
start1=source.index('## 1.');start2=source.index('## 3.');start3=source.index('## 4.')
hero='''<div class="eyebrow">PRODUCT GUIDE / 产品说明书</div><h1>包懂你<span>AI 背包导购助手</span></h1><p class="lead">把日常表达，转化为更清楚的选购方向。</p><div class="entry">体验入口　<a href="https://baodongni.onrender.com">baodongni.onrender.com ↗</a><span>体验版 · 文字导购</span></div>'''
css='''@page{size:A4;margin:17mm 17mm 18mm}*{box-sizing:border-box}body{font-family:"Noto Sans CJK SC","Noto Sans SC",sans-serif;color:#20202a;font-size:10pt;line-height:1.7;margin:0}a{color:#8c478b;text-decoration:none}h1{font-size:29pt;line-height:1.3;margin:8px 0 10px;font-weight:800;letter-spacing:1px}h1 span{font-size:15pt;display:block;font-weight:500;letter-spacing:0;margin-top:4px}h2{font-size:13pt;margin:18px 0 9px;line-height:1.5;break-after:avoid}h3{font-size:10.9pt;margin:15px 0 7px;line-height:1.5;break-after:avoid}p{margin:6px 0 9px;orphans:3;widows:3}table{width:100%;border-collapse:collapse;font-size:9.2pt;line-height:1.6;margin:10px 0 12px;break-inside:avoid}th{text-align:left;background:#f5eff7;color:#59365e;font-weight:600}td,th{padding:7px 10px;vertical-align:top;border-bottom:1px solid #e8e2eb}td:first-child{width:25%;font-weight:500}.eyebrow{color:#985392;font-size:9pt;letter-spacing:1px}.lead{color:#66616f;margin-bottom:13px}.entry{background:#f9f4fa;border-left:3px solid #b76ab4;padding:9px 12px;font-size:9.4pt;display:flex;gap:5px;align-items:center}.entry>span{margin-left:auto;color:#817889;font-size:8pt}.contents{display:flex;gap:22px;margin:16px 0 18px;padding:10px 0 12px;border-bottom:1px solid #e2d9e7;font-size:9pt}.contents>b{color:#754b7a}.contents>div{flex:1;display:grid;grid-template-columns:1fr 1fr;column-gap:22px}.contents p{display:flex;justify-content:space-between;margin:0 0 4px;gap:10px}.contents em{font-style:normal;color:#9c82a5}.page{break-after:page}.page:last-child{break-after:auto}.page-kicker{font-size:9pt;color:#98649b;letter-spacing:1px;border-bottom:1px solid #e7dfeb;padding-bottom:8px;margin-bottom:12px}.notice{border-left:3px solid #c18ab8;padding:8px 12px;background:#faf6fa;font-size:9.2pt;color:#5d5064;margin-top:15px}'''
html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>包懂你｜AI 背包导购助手产品说明书</title><style>'+css+'</style></head><body>'
html+='<section class="page">'+hero+block(source[start1:start2])+'</section>'
html+='<section class="page"><div class="page-kicker">包懂你 / 需求理解与选购参考</div>'+block(source[start2:start3])+'</section>'
html+='<section class="page"><div class="page-kicker">包懂你 / 商品数据与使用说明</div>'+block(source[start3:])+'<div class="notice">体验版商品资料用于功能体验。实际选购请以核实后的商家商品信息为准。</div></section></body></html>'
(ROOT/'docs/baodongni-product-manual.html').write_text(html)
print('Built docs/baodongni-product-manual.html')
