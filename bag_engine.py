"""Grounded backpack shopping: state edits, catalog search and evidence-bound answers.

The rule layer covers explicit constraints; a model supplies open-ended semantics and
optional wording. Model output cannot change the selected SKU set or catalog facts.
"""
import json,re,time,math,hashlib,difflib
from pathlib import Path

AESTHETICS=['清新少女','酷感机能','极简','复古','运动感','商务','活力撞色']
FEATURES=['宽肩带','电脑隔层','胸扣','行李箱插带','防盗口袋','水杯侧袋','背部透气','少分区']
CATEGORIES=['通勤电脑双肩包','学生护脊书包','休闲双肩包','户外登山包','托特包','斜挎包','胸包']
FIELDS=set(('scene','gender','style','budget','laptop','maxweight','capacity','color','water','storage','priority','needs_laptop','aesthetics','features','excluded_colors','category','water_need','material','protection'))
NUMBERS={'budget','laptop','maxweight','capacity'}
ARRAYS={'aesthetics','features','excluded_colors'}
COLORS={'蓝色':['雾霾蓝','海军蓝','浅蓝色','深蓝色','藏蓝色','蓝色','蓝的','蓝款','浅蓝','天蓝','深蓝','藏蓝','宝蓝','雾蓝','藏青'],'黑色':['黑色','黑的','纯黑'],'白色':['白色','白的','纯白'],'米色':['米白色','奶油白','米色','米白','奶白'],'粉色':['樱花粉','浅粉色','粉色','粉的','浅粉'],'紫色':['香芋紫','浅紫色','紫色','紫的','浅紫'],'绿色':['橄榄绿','绿色','绿的','军绿','墨绿','浅绿'],'灰色':['灰色','灰的','浅灰','深灰'],'橙色':['橙色','橘色','橙的'],'黄色':['黄色','黄的','姜黄'],'红色':['红色','红的','酒红']}
NEG=r'(?:不要|不想要|不喜欢|排除|别选|不能是|不要选)'

EXTRACTION='''你是中文购物对话的语义解析器。只解析用户本轮对需求的修改，不写推荐文案，不从历史重新添加已取消条件。当前状态由程序提供。
返回JSON：{"intent":"recommend|analysis|compare|chat","updates":{},"remove":[],"remove_features":[],"remove_aesthetics":[],"target_ids":[],"question_kind":"general|weight|capacity|fit|cons|pros|reviews|compare","skip":[]}。
updates可用：scene(校园/通勤/旅行/休闲/运动)、gender、budget(元)、laptop(英寸)、maxweight(克)、capacity(升，最低需求)、color(蓝色/黑色等)、excluded_colors数组、aesthetics数组、features数组、water_need(待确认/防泼水/日常防雨/有防水证明)、storage布尔、priority(轻便/收纳/保护/外观)、needs_laptop布尔、category、material、protection(air)。
风格：清新少女、酷感机能、极简、复古、运动感、商务、活力撞色。女生不等于少女/粉色/小包。功能：宽肩带、电脑隔层、胸扣、行李箱插带、防盗口袋、水杯侧袋、背部透气、少分区。外观简单是极简；找东西方便不翻多个隔层是少分区。
明确数值才设上限：轻便/轻一点只设priority=轻便，不凭空设600g。宽肩带是结构，不保证不累。泛称防水设待确认；短时水滴设防泼水，短时小雨设日常防雨，持续淋雨且普通防泼水不够设有防水证明。
删除要求必须用remove：预算不限删除budget，颜色随意删除color和excluded_colors，不带电脑了删除laptop、needs_laptop、protection并从features移除电脑隔层。取消防水删除water和water_need；不要求宽肩带了只移除features中的宽肩带，不能把其他功能清空。修改颜色是替换旧颜色，预算提高到300是替换旧预算。
用户推荐新商品时intent=recommend，不沿用上一轮analysis/compare。只问这款多重、缺点、评价是analysis；这两款/哪个更轻是compare。问候、感谢、知识问题是chat。target_ids仅可来自提供目录，指代不明时保留空数组，不猜另一款。
例：当前黑色预算200，用户“改成蓝色其他不变”→updates={"color":"蓝色"}。
例：当前laptop16、needs_laptop真、scene通勤，用户“周末出门，不带电脑了”→updates={"scene":"休闲"},remove=["laptop","needs_laptop","protection"],remove_features=["电脑隔层"]。
例：当前少女、粉色，用户“不要少女风了，换酷酷的，不限颜色”→updates={"aesthetics":["酷感机能"]},remove=["color","excluded_colors"],remove_aesthetics=["清新少女"]。
不要输出完整历史状态，不要给被删条件赋另一个默认值。'''

WRITER='''你是一个会帮朋友挑背包的中文导购。根据给定的回答蓝图改写得自然、具体、简洁。每个items.focus是这款本轮的介绍重点：必须围绕不同的产品差异组织句子，不把每段都写成重量＋容量＋日常好搭的换数字模板。不得复制其他段的完整句式。事实、商品顺序和商品ID不可改变。用户已在页面底部看到模拟数据说明，不要反复提示演示/截图/候选/已保留条件/不硬凑/不推荐。
推荐时只介绍选中商品本身及为什么符合需求，不谈其他商品哪里不好、不列淘汰理由、不塞不符合条件的商品。使用“日常带电脑，先看电脑仓的缓冲和空包重量。……这款430g，16英寸电脑有独立隔层，上课通勤都方便。”这样的消费者语言。
用户问缺点才直接说所选商品的具体取舍；问重量直接报重量；问比较就回答具体差别，不能答非所问。只用蓝图事实；不把宽肩带说成必然不累，不把防泼水说成长时防水，不编造认证、品牌承诺或优惠。不要提问，程序把必要追问放在最后。
返回JSON：{"opening":"简短开头","items":[{"id":整数,"text":"该商品介绍，1—3句"}],"closing":"可为空"}。items必须和蓝图items逐一对应，不能少、重复或换ID，不添加商品名以外的商品、价格、数字、属性。重要短语可用【】标记，最多3处。不输出Markdown星号或思考过程。'''


def load_catalog(root):
 rows=json.loads((Path(root)/'data/catalog.json').read_text(encoding='utf-8'))
 imported=Path(root)/'bag_products.json'
 if imported.exists():
  raw=json.loads(imported.read_text(encoding='utf-8-sig'))
  if not isinstance(raw,list):raise ValueError('bag_products.json must be an array')
  additions=[];seen=set()
  for r in raw[:500]:
   if not isinstance(r,dict) or not isinstance(r.get('name'),str) or not str(r.get('url','')).startswith('https://'):continue
   key=r.get('sku') or r['url']
   if key in seen:continue
   seen.add(key)
   p=dict(name=r['name'][:150],brand=r.get('brand','商品资料'),family=r.get('family',key),sku=r.get('sku',key),kind='provided',simulated=False,photo=None,photo_sheet=None,image_url='',url=r['url'],price=None,weight=None,capacity=None,laptop=None,dimensions='',material='',color='',color_label='',style='',style_tags=[],aesthetic_tags=[],categories=[],scene=[],feature_flags={},water_protection=None,water=None,storage=None,computer_padding=None,rating=None,sales=None,review_count=None,reviews=[],advantages=[],limits=[],source=r.get('source','录入商品资料'),service_tags=[],shop_name=r.get('shop_name',r.get('brand','商品店铺')),shipping='',stock=None,variants=[])
   for k,v in r.items():
    if k in p and k not in ('id','simulated','kind'):p[k]=v
   p['image_url']=p['image_url'] if str(p['image_url']).startswith('https://') else ''
   additions.append(p)
  import os
  rows=additions if os.getenv('BAG_CATALOG_ONLY','').lower() in ('1','true','yes') else rows+additions
 else:
  import os
  if os.getenv('BAG_CATALOG_ONLY','').lower() in ('1','true','yes'):rows=[]
 for i,p in enumerate(rows):p['id']=i
 return rows


def clean(raw):
 out={}
 if not isinstance(raw,dict):return out
 for k,v in raw.items():
  if k not in FIELDS:continue
  if k in NUMBERS:
   if type(v) in (int,float) and math.isfinite(v) and 0<=v<=100000:out[k]=v
  elif k in ARRAYS:
   allowed=AESTHETICS if k=='aesthetics' else FEATURES if k=='features' else COLORS
   if isinstance(v,list):out[k]=list(dict.fromkeys(x for x in v if x in allowed))
  elif k in ('water','storage','needs_laptop'):
   if type(v)==bool:out[k]=v
  elif isinstance(v,str) and v and len(v)<=40:
   if k=='color':
    found=colors_in(v);out[k]=found[-1][2] if found else v
   elif k=='scene':out[k]={'上班':'通勤','工作':'通勤','商务':'通勤','大学生':'校园','上课':'校园','日常':'休闲','逛街':'休闲','出差':'旅行','户外':'旅行'}.get(v,v)
   elif k=='style':
    if v in ('简约','商务','运动','休闲'):out[k]=v
   else:out[k]=v
 return out


def colors_in(text):
 hits=[]
 for canonical,aliases in COLORS.items():
  for alias in aliases:
   for m in re.finditer(re.escape(alias),text):
    negative=bool(re.search(NEG+r'.{0,3}$',text[max(0,m.start()-8):m.start()]))
    hits.append((m.start(),m.end(),canonical,negative))
 # Prefer the longest alias at the same location, don't count its substrings twice.
 hits.sort(key=lambda x:(x[0],-(x[1]-x[0])))
 result=[];end=-1
 for h in hits:
  if h[0]>=end:result.append(h);end=h[1]
 return result


def local_patch(text,current=None):
 """Explicit customer edits. No inference of gender, arbitrary budgets or weight caps."""
 c=current or {};t=text.strip();updates={};remove=set();rf=set();ra=set();skip=set();kind='general'
 def cancel(pattern,*fields):
  if re.search(pattern,t):remove.update(fields);skip.update(fields)
 cancel(r'(?:不要|不需要|去掉|取消).{0,4}(?:预算|价格)(?:要求|条件|限制)?(?:了|啦)?$','budget')
 cancel(r'(?:不要|不需要|去掉|取消).{0,4}(?:颜色|配色)(?:要求|条件|限制)(?:了|啦)?','color','excluded_colors')
 cancel(r'(?:不要求|不需要).{0,4}(?:蓝色|黑色|粉色|白色|米色|紫色|绿色|灰色)(?:了|啦)|(?:不要|取消|去掉).{0,4}(?:蓝色|黑色|粉色|白色|米色|紫色|绿色|灰色)(?:这个)?(?:条件|要求|限制)','color')
 cancel(r'预算(?:不(?:限|限制|重要)|随意|取消)|(?:不限|不限制|取消|去掉)(?:预算|价格)|(?:不用|不必|别)(?:再)?(?:管|考虑|限制)(?:预算|价格)', 'budget')
 cancel(r'(?:颜色|配色)(?:不(?:限|限制|挑|重要)|随意|都行|无所谓)|(?:取消|去掉)(?:颜色|配色)(?:要求|条件|限制)?|(?:不用|不必)(?:再)?(?:管|考虑|限制)(?:颜色|配色)', 'color','excluded_colors')
 cancel(r'(?:不(?:需要|要求)|不用|取消|去掉).{0,3}防水|防水(?:不重要|无所谓|算了|不要了|不用了)|不需要防雨','water','water_need')
 cancel(r'(?:不(?:需要|要求)|取消|去掉).{0,3}(?:轻便|重量|轻量)|(?:重量|轻便)(?:不重要|无所谓|不限|不用管|不用考虑)|不用(?:管|考虑)重量','maxweight')
 cancel(r'(?:不(?:需要|要求)|不用|取消|去掉).{0,3}容量|容量(?:不限|不限制|无所谓)','capacity')
 size_cancel=bool(re.search(r'(?:取消|去掉|不要求).{0,3}电脑尺寸|电脑尺寸(?:不限|不限制)',t))
 if size_cancel:remove.add('laptop');skip.add('laptop')
 if not size_cancel and re.search(r'不带(?:笔记本|电脑)|不用带(?:笔记本|电脑)|不(?:需要|要求)(?:电脑仓|电脑隔层|装电脑)|取消电脑|(?:不需要|不要求|不要)(?:带|装)?(?:笔记本|电脑)(?:了|的要求|要求|这个条件)?',t):
  remove.update(('laptop','needs_laptop','protection'));rf.add('电脑隔层');skip.add('laptop')
  if c.get('priority')=='保护':remove.add('priority')
 if 'maxweight' in remove and c.get('priority')=='轻便':remove.add('priority')
 if re.search(r'(?:风格|款式)(?:不限|不限制|随意|都行)|(?:取消|去掉)风格(?:限制|要求)?',t):remove.update(('aesthetics','style'))
 # A new explicit value replaces old state; removals never repopulate from history.
 for a,b,color,negative in colors_in(t):
  if negative and 'color' not in remove:updates['excluded_colors']=list(dict.fromkeys(updates.get('excluded_colors',c.get('excluded_colors',[]))+[color]))
  elif 'color' not in remove:updates['color']=color
 if updates.get('color'):
  updates['excluded_colors']=[v for v in updates.get('excluded_colors',c.get('excluded_colors',[])) if v!=updates['color']]
 amounts=list(re.finditer(r'(?:预算|价格|价位|不超过|不高于|控制在|最多|至多|提高到|降到|涨到|改到|改成)\s*(?:希望|想|最好|可以|能|控制在|提高到|降到|为|到|是|在|以内|不超过|不高于|可以提高到|可以到|提高至|能到|限制在)*\s*(\d+(?:\.\d+)?)\s*(?:元|块|以内|以下|左右)?',t))
 if not amounts:amounts=list(re.finditer(r'(\d+(?:\.\d+)?)\s*(?:元|块)(?:钱)?(?:以内|以下|左右)',t))
 amounts=[m for m in amounts if not re.match(r'(?:克|公斤|千克|[gG]|[kK][gG]|升|[lL]|英寸|寸)',t[m.end():])]
 if amounts and 'budget' not in remove:updates['budget']=float(amounts[-1].group(1))
 # Chinese whole-hundred budget words commonly used in conversation.
 for word,value in [('一百',100),('两百',200),('二百',200),('三百',300),('五百',500),('一千',1000)]:
  if re.search(r'(?:预算|价格|价位).{0,5}'+word,t) and 'budget' not in remove:updates['budget']=value
 weight=re.search(r'(?:不超过|不高于|最多|至多|控制在|低于|小于|轻于|最好)?\s*(\d+(?:\.\d+)?)\s*(公斤|千克|kg|KG|克|g|G)(?:以内|以下)?',t)
 if weight and 'maxweight' not in remove:
  updates['maxweight']=float(weight.group(1))*(1000 if weight.group(2) in ('公斤','千克','kg','KG') else 1)
 capacity=re.search(r'(\d+(?:\.\d+)?)\s*(?:升|[lL])(?:以上|左右|容量)?',t)
 if capacity and 'capacity' not in remove:updates['capacity']=float(capacity.group(1))
 laptop=re.search(r'(\d+(?:\.\d+)?)\s*(?:英寸|寸)',t)
 if laptop and 'laptop' not in remove:updates.update(laptop=float(laptop.group(1)),needs_laptop=True)
 if re.search(r'带(?:着)?(?:笔记本|电脑)|装(?:笔记本|电脑)|电脑通勤|电脑和书|电脑贵|怕磕碰|游戏本',t) and 'needs_laptop' not in remove:updates['needs_laptop']=True
 if re.search(r'电脑(?:贵|保护)|怕磕碰|防震|缓震|气囊',t) and 'protection' not in remove:updates.update(protection='air',priority='保护',needs_laptop=True)
 scenes=[('校园',r'上课|大学生|校园|装书|书本|学生'),('通勤',r'上班|通勤|工作|办公室'),('旅行',r'出差|旅游|旅行|徒步|登山|露营'),('运动',r'健身|打球|运动'),('休闲',r'周末|逛街|出门玩|日常出门')]
 found=[]
 for scene,pattern in scenes:
  for m in re.finditer(pattern,t):
   if not re.search(r'(?:不再|不用|不去|不用于).{0,2}$',t[max(0,m.start()-6):m.start()]):found.append((m.start(),scene))
 if found:updates['scene']=max(found)[1]
 if re.search(r'女生|女孩子|女性',t):updates['gender']='女生'
 if re.search(r'男生|男性',t):updates['gender']='男生'
 styles=[('清新少女',r'少女|甜美|软萌|可爱|轻甜'),('酷感机能',r'酷酷|酷感|酷一点|机能风|机能感|酷的'),('极简',r'简约|极简|外观简单|款式简单|少装饰|干净一点'),('复古',r'复古'),('运动感',r'运动风|运动感'),('商务',r'商务风|正式一点'),('活力撞色',r'撞色|拼色')]
 positive=[]
 for tag,pattern in styles:
  for m in re.finditer(pattern,t):
   prefix=t[max(0,m.start()-7):m.start()]
   if re.search(NEG+r'.{0,3}$|(?:不用|不需要|不要求|取消).{0,3}$',prefix):ra.add(tag)
   else:positive.append(tag)
 if positive and 'aesthetics' not in remove:updates['aesthetics']=list(dict.fromkeys(positive));remove.add('style')
 feature_patterns={'宽肩带':r'宽肩带|肩带宽|宽背带','电脑隔层':r'独立电脑(?:仓|隔层)|电脑分隔','胸扣':r'胸扣|胸带','行李箱插带':r'行李箱插带|拉杆插带|套行李箱|套在行李箱','防盗口袋':r'防盗(?:口袋|袋)','水杯侧袋':r'水杯侧袋|侧面放水杯','背部透气':r'背部透气|背板透气','少分区':r'分区简单|分区少|少分区|不想.{0,12}好几个隔层|不要.{0,5}(?:很多|太多)(?:口袋|隔层|分区)|外观不要.{0,5}(?:很多|太多)口袋'}
 fp=list(c.get('features',[]));changed=False
 for f,pattern in feature_patterns.items():
  for m in re.finditer(pattern,t):
   prefix=t[max(0,m.start()-8):m.start()];ending=t[m.end():m.end()+5]
   if re.search(r'(?:不需要|不要求|不用|取消|去掉|不要).{0,3}$',prefix) or re.match(r'(?:不要了|不用了|不重要|算了)',ending):rf.add(f)
   else:
    if f not in fp:fp.append(f)
    changed=True
 if changed:updates['features']=fp
 if re.search(r'分区多|收纳多|分区清晰|收纳分区多',t):updates.update(storage=True,priority='收纳')
 if re.search(r'(?:不需要|不用|不要求).{0,3}(?:分区多|收纳多)|分区多.{0,2}(?:算了|不要了)',t):remove.add('storage')
 if re.search(r'轻便|轻一点|轻一些|轻量|更轻|背着轻|不超过\s*\d+\s*克',t) and 'maxweight' not in remove:updates['priority']='轻便'
 if 'water_need' not in remove:
  if re.search(r'长时间淋雨|持续淋雨|大雨|暴雨|防水测试证明|防水证明|完全防水',t):updates['water_need']='有防水证明'
  elif re.search(r'小雨|短时.{0,3}雨|日常防雨',t):updates['water_need']='日常防雨'
  elif re.search(r'防泼水|短时.{0,3}水滴|水滴',t):updates['water_need']='防泼水'
  elif re.search(r'防水|淋雨',t):updates['water_need']='待确认'
 for cat,pattern in [('托特包',r'托特'),('斜挎包',r'斜挎'),('胸包',r'胸包'),('户外登山包',r'登山包|徒步包'),('学生护脊书包',r'护脊书包')]:
  if re.search(pattern,t):updates['category']=cat
 if re.search(r'(?:背包|双肩包)就行|不限(?:包型|品类)|取消品类',t):remove.add('category')
 if re.search(r'帆布|尼龙|牛津布',t):updates['material']=re.search(r'帆布|尼龙|牛津布',t).group()
 if re.search(r'面料(?:不限|不限制|无所谓)|取消面料',t):remove.add('material')
 # Plain named preferences from a question-option count as a recommendation edit.
 edited=bool(updates or remove or rf or ra)
 recommend=bool(re.search(r'推荐|帮.{0,3}选|想买|想要|找.{0,5}包|换(?:成|个|一款)|预算|其他(?:要求)?不变|不要.{0,8}了',t)) or edited
 compare=bool(re.search(r'这两|这几|比较|对比|哪个|哪款更|相差',t))
 analysis=bool(re.search(r'这款|这个商品|分析商品|缺点|不足|评价|多重|重量|容量多大|适合每天|适合带',t))
 if re.search(r'多重|重量|多少克|更轻|相差.*克',t):kind='weight'
 elif re.search(r'容量多大|多少升|容量多少',t):kind='capacity'
 elif re.search(r'缺点|不足|不满意|留意',t):kind='cons'
 elif re.search(r'评价|好评|大家.*夸|评论',t):kind='reviews'
 elif re.search(r'优点|优势',t):kind='pros'
 elif re.search(r'装下|带电脑|带.{0,3}电脑|适合每天|电脑通勤',t):kind='fit'
 direct_recommend=bool(re.search(r'推荐|换一款|帮.{0,3}选|想买',t))
 intent='compare' if compare else 'recommend' if direct_recommend else 'analysis' if analysis else 'recommend' if recommend else 'chat'
 # Direct follow-up answers like "蓝色" are edits, not an analysis of the old SKU.
 if edited and not compare and not re.search(r'这款|这两|这个商品|评价|缺点|不足|多少|多重|好看吗',t):intent='recommend'
 if re.search(r'评价|评论',t):kind='reviews'
 return dict(intent=intent,updates=clean(updates),remove=list(remove),remove_features=list(rf),remove_aesthetics=list(ra),target_ids=[],question_kind=kind,skip=list(skip),explicit=edited)


def merge_state(current,patch):
 c=clean(current)
 remove=set(k for k in patch.get('remove',[]) if k in FIELDS)
 for k in remove:c.pop(k,None)
 for k,v in clean(patch.get('updates',patch.get('changes',{}))).items():
  if k not in remove:c[k]=v
 for key,removed in [('features',patch.get('remove_features',[])),('aesthetics',patch.get('remove_aesthetics',[]))]:
  if removed:
   c[key]=[v for v in c.get(key,[]) if v not in removed]
   if not c[key]:c.pop(key,None)
 if 'style' in remove:c.pop('style',None)
 for tag,style in [('极简','简约'),('商务','商务'),('运动感','运动')]:
  if tag in patch.get('remove_aesthetics',[]) and c.get('style')==style:c.pop('style',None)
 if ('needs_laptop' in remove or patch.get('updates',{}).get('needs_laptop') is False) and not c.get('needs_laptop'):
  c.pop('laptop',None);c.pop('protection',None)
  if 'features' in c:c['features']=[v for v in c['features'] if v!='电脑隔层']
 if c.get('color') in c.get('excluded_colors',[]):c['excluded_colors']=[v for v in c['excluded_colors'] if v!=c['color']]
 return c


def combine_patches(model,explicit):
 out={**model,'updates':{**model.get('updates',model.get('changes',{})),**explicit.get('updates',{})}}
 for k in ('remove','remove_features','remove_aesthetics','skip'):
  out[k]=list(dict.fromkeys(model.get(k,[])+explicit.get(k,[])))
 # Explicit direct customer values override a stale model removal, except local cancellations.
 out['remove']=[k for k in out['remove'] if k not in explicit.get('updates',{}) or k in explicit.get('remove',[])]
 if explicit.get('explicit') or explicit['intent'] in ('analysis','compare'):out['intent']=explicit['intent']
 if explicit['question_kind']!='general':out['question_kind']=explicit['question_kind']
 return out


def match(p,c):
 reasons=[]
 for k,pk,upper in [('budget','price',True),('maxweight','weight',True),('capacity','capacity',False),('laptop','laptop',False)]:
  if c.get(k) is not None:
   v=p.get(pk)
   if v is None or (v>c[k] if upper else v<c[k]):reasons.append(k)
 if c.get('needs_laptop') and p.get('feature_flags',{}).get('电脑隔层') is not True:reasons.append('needs_laptop')
 if c.get('color') and p.get('color')!=c['color']:reasons.append('color')
 if p.get('color') in c.get('excluded_colors',[]):reasons.append('excluded_colors')
 for tag in c.get('aesthetics',[]):
  if tag not in p.get('aesthetic_tags',[]):reasons.append('aesthetics')
 if c.get('style') and c['style'] not in p.get('style_tags',[]):reasons.append('style')
 for flag in c.get('features',[]):
  if p.get('feature_flags',{}).get(flag) is not True:reasons.append('features')
 if c.get('scene') and c['scene'] not in p.get('scene',[]):reasons.append('scene')
 if c.get('category') and c['category'] not in p.get('categories',[]):reasons.append('category')
 if c.get('storage') and not p.get('storage'):reasons.append('storage')
 if c.get('material') and c['material'] not in p.get('material',''):reasons.append('material')
 if c.get('protection')=='air' and p.get('computer_padding')!='air':reasons.append('protection')
 levels={'防泼水':1,'日常防雨':2,'有防水证明':3}
 if c.get('water_need') not in (None,'','待确认') and levels.get(p.get('water_protection'),0)<levels.get(c['water_need'],99):reasons.append('water_need')
 if c.get('water') and levels.get(p.get('water_protection'),0)<1:reasons.append('water')
 return not reasons,reasons


def rank(p,c):
 reputation=(p.get('rating') or 0)/100*2+math.log1p(p.get('sales') or 0)/10
 score=reputation
 if c.get('priority')=='轻便':score-=float(p.get('weight') or 2000)/180
 elif c.get('priority')=='保护':score+=3 if p.get('computer_padding')=='air' else 0
 elif c.get('priority')=='收纳':score+=2 if p.get('storage') else 0
 elif c.get('aesthetics'):score+=len(set(c['aesthetics'])&set(p.get('aesthetic_tags',[])))
 if c.get('needs_laptop') and not c.get('priority'):score-=float(p.get('weight') or 1500)/1000;score+=.6 if p.get('computer_padding')=='air' else 0
 return score


def search(goods,c):
 pool=[p for p in goods if match(p,c)[0] and (c.get('category') or any(cat in p.get('categories',[]) for cat in ('通勤电脑双肩包','学生护脊书包','休闲双肩包','户外登山包')))]
 pool.sort(key=lambda p:(rank(p,c),-p['id']),reverse=True)
 # Each catalog entry has its own SKU and image; don't return aliases of the same family.
 seen=set();out=[]
 for p in pool:
  key=p.get('family') or p.get('sku') or p['name']
  if key not in seen:out.append(p);seen.add(key)
 return out


def followup(c,asked,skip):
 checks=[]
 if c.get('water_need')=='待确认':checks.append(('water_need','你希望应付短时水滴，还是经常在雨里走？',['防泼水就可以','需要日常防雨','需要有防水测试证明']))
 checks += [('scene','平时主要背去上课、上班，还是出门玩？',['上课和校园日常','上班通勤','周末出门玩']),('budget','预算大概想控制在多少以内？',['150元以内','300元以内','预算不限'])]
 if c.get('needs_laptop'):checks.append(('laptop','平时带的是多大尺寸的电脑？',['14英寸','16英寸','17.3英寸']))
 for k,q,choices in checks:
  if (not c.get(k) or k=='water_need' and c.get(k)=='待确认') and k not in asked and k not in skip:return k,q,choices
 return '', '', []


def number(v,unit=''):
 return f'{v:g}{unit}' if type(v) in (int,float) else '资料未提供'


def product_angles(p,c):
 flags=p.get('feature_flags',{});w=number(p.get('weight'),'g');cap=number(p.get('capacity'),'L');size=number(p.get('laptop'),'英寸')
 angles={'design':p.get('design_note','适合日常携带的简洁轮廓')+'。'}
 if p.get('weight') is not None and p['weight']<=450:angles['weight']=f'【空包{w}】，日常只带书本或随身物品时，可以少带一些包体自重。'
 if p.get('computer_padding')=='air':angles['padding']=f'【{size}加厚缓冲电脑仓】，把设备与其他物品分开收好，适合每天带电脑往返。'
 if p.get('capacity') is not None and p['capacity']>=25:angles['space']=f'【{cap}主仓】，上课或上班之外还要带外套、配件时，收纳余地更充足。'
 if flags.get('行李箱插带'):angles['luggage']='需要兼顾出差的话，背部的【行李箱插带】可以把背包固定在拉杆上，转乘时少占一只手。'
 if flags.get('少分区'):angles['simple']='收纳结构偏简单，拿东西不用逐层翻找，适合不想记太多口袋位置的用法。'
 if flags.get('宽肩带'):angles['straps']=f'{number(p.get("shoulder_width_cm"),"cm")}宽肩带，肩部接触面积更大，适合会装书本或设备的日常。'
 if c.get('budget') is not None and p.get('price') is not None:angles['value']=f'{number(p["price"],"元")}价位，先把预算放在每天会用到的收纳和携带功能上。'
 water=p.get('water_protection')
 if water=='有防水证明':angles['rain']='闭合包体有【IPX6防喷水测试记录】，更适合雨天户外使用。'
 elif water=='日常防雨':angles['rain']='通勤路上常遇到小雨，可以看看这款的【日常防雨结构】。'
 order=['design','weight','simple','space','straps','luggage','rain','value','padding']
 if c.get('needs_laptop') or c.get('laptop') or c.get('scene')=='通勤':order=['padding','weight','space','luggage','simple','rain','design','straps','value']
 if c.get('priority')=='轻便' or c.get('maxweight') is not None:order=['weight','design','simple','space','straps','rain','value','padding','luggage']
 if c.get('water_need') not in (None,'','待确认'):order=['rain','design','space','straps','weight','padding','luggage','simple','value']
 return angles,order


def recommendation_text(p,c,index=0,focus=None):
 """Lead with a real product distinction; preserve every explicit matching reason."""
 angles,order=product_angles(p,c)
 focus=focus if focus in angles else next(k for k in order if k in angles)
 parts=[angles[focus]];laptop=c.get('needs_laptop') or c.get('laptop') or c.get('scene')=='通勤'
 size=number(p.get('laptop'),'英寸');pad='加厚缓冲电脑仓' if p.get('computer_padding')=='air' else '独立电脑隔层'
 if laptop and p.get('laptop') is not None and focus!='padding':parts.append(f'标称适配{size}电脑，设有{pad}。')
 if (c.get('priority')=='轻便' or c.get('maxweight') is not None) and focus!='weight':parts.append(f'空包{number(p.get("weight"),"g")}。')
 if c.get('color') and (p.get('color_label') or p.get('color')) not in parts[0]:parts.append(f'这一款是{p.get("color_label") or p.get("color")}配色。')
 if c.get('aesthetics') and focus!='design':parts.append(p.get('design_note','')+'。')
 if '宽肩带' in c.get('features',[]) and focus!='straps':parts.append(f'{number(p.get("shoulder_width_cm"),"cm")}宽肩带，接触面积更大。')
 if '少分区' in c.get('features',[]) and focus!='simple':parts.append('分区数量少，物品拿取路径直接。')
 if c.get('storage') and focus not in ('space','padding'):parts.append('电脑、配件和小物品可以分区收好。')
 if c.get('water_need') not in (None,'','待确认') and focus!='rain':
  water=p.get('water_protection');parts.append('闭合包体有IPX6防喷水测试记录。' if water=='有防水证明' else '结构适合短时小雨。' if water=='日常防雨' else '面料可以应付日常水滴。')
 if len(parts)==1:
  if focus!='design':parts.append(p.get('design_note','')+'。')
  elif p.get('laptop') is not None:parts.append(f'{number(p.get("capacity"),"L")}容量，{size}电脑有单独收纳位置。')
  else:parts.append(f'包身{number(p.get("weight"),"g")}、容量{number(p.get("capacity"),"L")}，适合轻装随行。')
 return ''.join(part for part in parts if part and part!='。')


def recommendation_items(products,c):
 usage={};items=[]
 for index,p in enumerate(products):
  angles,order=product_angles(p,c)
  focus=min((k for k in order if k in angles),key=lambda k:(usage.get(k,0),order.index(k)))
  usage[focus]=usage.get(focus,0)+1
  items.append(dict(id=p['id'],text=recommendation_text(p,c,index,focus),focus=focus))
 return items


def kind_from_text(text):
 t=text
 if re.search(r'多重|重量|多少克|更轻|相差.*克',t):return 'weight'
 if re.search(r'容量多大|多少升|容量多少',t):return 'capacity'
 if re.search(r'评价|好评|大家.*夸|评论',t):return 'reviews'
 if re.search(r'缺点|不足|不满意|留意',t):return 'cons'
 if re.search(r'优点|优势',t):return 'pros'
 if re.search(r'电脑|装下|适合每天',t):return 'fit'
 return 'general'


def item_answer(p,kind,text,c):
 if kind=='weight':return f"【空包{number(p.get('weight'),'g')}】。"+(f"容量{number(p.get('capacity'),'L')}，适合日常轻装携带。" if p.get('capacity') is not None else '')
 if kind=='capacity':return f"容量是【{number(p.get('capacity'),'L')}】，外形尺寸{p.get('dimensions') or '资料未提供'}。"
 if kind=='cons':return '主要需要留意的是：'+ '；'.join(p.get('limits',[])[:2])+'。'
 if kind=='reviews':
  reviews=[r if isinstance(r,str) else r.get('text','') for r in p.get('reviews',[])]
  return (f"好评率【{number(p.get('rating'),'%')}】，共{number(p.get('review_count'),'条评价')}。" if p.get('rating') is not None else '')+('评价里提到：'+ '；'.join(reviews[:3]) if reviews else '目前没有评论正文。')
 if kind=='fit':
  if p.get('laptop') is not None:
   size=c.get('laptop');fits=size is None or size<=p['laptop']
   if not fits:return f"这款标称适配{number(p['laptop'],'英寸')}电脑，你的{number(size,'英寸')}电脑需要更大的内仓，尺寸不能直接保证装下。"
   pad='加厚缓冲电脑仓' if p.get('computer_padding')=='air' else '独立电脑隔层'
   return f"【可以用于日常带电脑】。标称{number(p['laptop'],'英寸')}{pad}，空包{number(p.get('weight'),'g')}，{number(p.get('capacity'),'L')}容量。电脑外壳尺寸仍需和内仓核对。"
  return '这款没有独立缓冲电脑隔层，平时装随身物品更合适；带电脑时需要额外内胆保护。'
 if kind=='pros':return '主要优点是：'+'；'.join(p.get('advantages',[])[:3])+'。'
 return recommendation_text(p,c)+'需要留意：'+'；'.join(p.get('limits',[])[:1])+'。'


def blueprint(intent,products,primary,backup,c,text,kind='general'):
 if intent=='recommend':
  if not primary:return dict(opening='这些要求放在一起，目前没有对应的款式。',items=[],closing='')
  if c.get('needs_laptop') or c.get('laptop') or c.get('scene')=='通勤':opening='每天带电脑，主要看【电脑仓的缓冲和空包重量】。这几款各有侧重，可以从你平时带的东西来选。'
  elif c.get('color'):opening=f"这几款{c['color']}背包可以先看看，包型和收纳各有特点。"
  elif c.get('aesthetics'):opening='这几款的外观比较贴近你想要的感觉，下面把各自适合的日常用法说清楚。'
  else:opening='先看这几款，日常携带、收纳和外观各有侧重。'
  return dict(opening=opening,items=recommendation_items(products,c),closing='')
 if intent=='analysis':return dict(opening='',items=[dict(id=p['id'],text=item_answer(p,kind,text,c)) for p in products],closing='')
 if intent=='compare':
  opening='';ps=products
  if kind=='weight' and all(p.get('weight') is not None for p in ps):
   ordered=sorted(ps,key=lambda p:p['weight']);delta=ordered[-1]['weight']-ordered[0]['weight']
   opening=f"更轻的是【{ordered[0]['name']}】，空包{number(ordered[0]['weight'],'g')}；"+ ('两款' if len(ps)==2 else '最轻与最重')+f"相差{number(delta,'g')}。"
  elif re.search(r'带电脑|电脑|通勤',text):
   winner=max(ps,key=lambda p:((p.get('laptop') or 0)>=c.get('laptop',0),p.get('computer_padding')=='air',-(p.get('weight') or 2000)))
   opening=f"每天带电脑，我会先选【{winner['name']}】。"+('它有加厚缓冲电脑仓，适合看重设备保护的通勤习惯。' if winner.get('computer_padding')=='air' else '它的电脑隔层和空包重量更适合日常携带。')
  else:opening='下面直接看各自的使用特点和参数差别。'
  return dict(opening=opening,items=[dict(id=p['id'],text=item_answer(p,kind,text,c)) for p in ps],closing='')
 return dict(opening='',items=[],closing='')


def safe_json(raw):
 if not isinstance(raw,str):raise ValueError('not text')
 start=raw.find('{')
 if start<0:raise ValueError('missing object')
 obj,_=json.JSONDecoder().raw_decode(raw[start:])
 if not isinstance(obj,dict):raise ValueError('not object')
 return obj


def suggestion_bank(intent,text,history):
 choices=['这款的主要优点是什么','这款的评价里有哪些常见反馈','我想换成更轻的款式'] if intent=='analysis' else ['哪款空包更轻','哪款适合每天带电脑','换一组符合要求的看看'] if intent=='recommend' else ['这几款的重量分别是多少','哪款分区更简单','我想重新选一款背包']
 def key(t):return re.sub(r'[\s\W]|请|帮我|一下|的|呢|吗','',t)
 seen=[key(text)]+[key(x.get('content','')) for x in history if x.get('role')=='user']
 return [s for s in choices if all(key(s)!=x and not (len(x)>4 and (x in key(s) or key(s) in x)) for x in seen)][:3]


class Engine:
 def __init__(self,goods,completion):self.goods=goods;self.completion=completion
 def ids(self,values):return list(dict.fromkeys(v for v in values if type(v)==int and 0<=v<len(self.goods)))[:12] if isinstance(values,list) else []
 def interpret(self,text,c,history,targets,visible,deadline):
  local=local_patch(text,c)
  prior_question=next((m.get('content','') for m in reversed(history) if m.get('role')=='assistant'),'')
  short_number=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:元|块|以内|以下|左右)?[。！!\s]*',text)
  if short_number and '预算' in prior_question and not local['explicit']:
   local['updates']['budget']=float(short_number.group(1));local['explicit']=True;local['intent']='recommend'
  context={'current_state':c,'selected_ids':targets,'visible_ids':visible,'catalog':[{'id':p['id'],'name':p['name']} for p in self.goods]}
  try:raw=self.completion([{'role':'system','content':EXTRACTION},{'role':'system','content':json.dumps(context,ensure_ascii=False)}]+history[-4:]+[{'role':'user','content':text}],deadline,True,1600)
  except Exception as error:
   if local['explicit'] and getattr(error,'status',500)>=500:return local,'explicit-model-unavailable'
   raise
  try:model=safe_json(raw)
  except ValueError:
   # Explicit edits can be applied without inventing or resurrecting a condition.
   if local['explicit'] or local['intent'] in ('analysis','compare'):return local,'explicit'
   raise ValueError('这次没有解析清楚需求，请换一句说法后重试。')
  if model.get('intent') not in ('recommend','analysis','compare','chat'):model['intent']=local['intent']
  for key in ('remove','remove_features','remove_aesthetics','target_ids','skip'):
   if not isinstance(model.get(key),list):model[key]=[]
   allowed=FEATURES if key=='remove_features' else AESTHETICS if key=='remove_aesthetics' else FIELDS if key in ('remove','skip') else None
   if allowed is not None:model[key]=[v for v in model[key] if isinstance(v,str) and v in allowed]
  if not isinstance(model.get('updates',model.get('changes',{})),dict):model['updates']={}
  for key,value in model.get('updates',model.get('changes',{})).items():
   if key in FIELDS and (value is None or value==''):model['remove'].append(key)
  if local['explicit'] and (re.search(r'(?:其他|其余).{0,4}不变',text) or re.fullmatch(r'[预算价格价位可以希望提高到降成控制为是在元块钱以内左右更不限制多少0123456789.，。\s]+',text)):
   return local,'explicit-preserve-other-conditions'
  combined=combine_patches(model,local)
  if local.get('updates',{}).get('priority')=='轻便' and 'maxweight' not in local['updates']:combined['updates'].pop('maxweight',None)
  return combined,'model+explicit'
 def validated_wording(self,plan,context,deadline):
  if not plan['items']:return plan,False
  fact_keys=('id','name','price','weight','capacity','laptop','color','color_label','material','computer_padding','feature_flags','shoulder_width_cm','water_protection','water_test','rating','sales','advantages','design_note','display_title')
  writer_facts=[{k:p.get(k) for k in fact_keys} for p in context]
  try:raw=self.completion([{'role':'system','content':WRITER},{'role':'user','content':json.dumps({'blueprint':plan,'facts':writer_facts},ensure_ascii=False)}],deadline,True,2800)
  except Exception as error:
   if getattr(error,'status',500)<500:raise
   return plan,False
  try:
   draft=safe_json(raw);items=draft.get('items');expected=[i['id'] for i in plan['items']]
   if not isinstance(items,list) or [i.get('id') for i in items if isinstance(i,dict)]!=expected:raise ValueError('IDs changed')
   for key in ('opening','closing'):
    if not isinstance(draft.get(key,''),str):raise ValueError('bad text')
   all_facts=json.dumps(context,ensure_ascii=False)
   for item in items:
    p=next(p for p in context if p['id']==item['id']);text=item.get('text')
    if not isinstance(text,str) or not text.strip() or len(text)>650:raise ValueError('bad item')
    evidence=[p.get('color_label'),p.get('color'),p.get('material')]+[number(p.get(k),u) for k,u in [('weight','g'),('capacity','L'),('laptop','英寸')] if p.get(k) is not None]+[f for f,v in p.get('feature_flags',{}).items() if v]
    if not any(token and token in text for token in evidence):raise ValueError('no supporting facts')
    allowed=set(re.findall(r'\d+(?:\.\d+)?',json.dumps(p,ensure_ascii=False)))
    if any(n not in allowed for n in re.findall(r'\d+(?:\.\d+)?',text)):raise ValueError('new numbers')
    for pattern,field in [(r'(\d+(?:\.\d+)?)\s*元','price'),(r'(\d+(?:\.\d+)?)\s*(?:g|克)', 'weight'),(r'(\d+(?:\.\d+)?)\s*(?:L|升)','capacity'),(r'(\d+(?:\.\d+)?)\s*(?:英寸|寸)','laptop'),(r'(\d+(?:\.\d+)?)\s*%','rating')]:
     if any(p.get(field) is None or float(v)!=float(p[field]) for v in re.findall(pattern,text)):raise ValueError('wrong unit value')
    if re.search(r'不推荐|其他.{0,8}(?:不适合|不好)|截图|候选|硬凑|已保留|无脑|闭眼入|不累|不勒|绝对防水',text):raise ValueError('sales script')
    for other in self.goods:
     if other['id']!=p['id'] and other['name'] in text:raise ValueError('wrong SKU')
    for color in COLORS:
     if color in text and color!=p.get('color'):raise ValueError('wrong color')
    for feature in ('宽肩带','电脑隔层','胸扣','行李箱插带','防盗口袋','水杯侧袋'):
     if feature in text and p.get('feature_flags',{}).get(feature) is not True and not re.search(r'(?:没有|无|未设|不带|不提供).{0,3}'+feature,text):raise ValueError('feature claim')
    for material in ('帆布','牛津布','皮革'):
     if material in text and material not in p.get('material',''):raise ValueError('material claim')
    if any(p.get('price') is None or float(v)!=float(p['price']) for v in re.findall(r'[¥￥]\s*(\d+(?:\.\d+)?)',text)):raise ValueError('price claim')
    if re.search(r'长时间淋雨|完全防水|IPX',text) and p.get('water_protection')!='有防水证明':raise ValueError('water claim')
    if re.search(r'加厚缓冲|气囊',text) and p.get('computer_padding')!='air':raise ValueError('padding claim')
   normalized=[]
   color_words=sorted({word for values in COLORS.values() for word in values},key=len,reverse=True)
   for item in items:
    plain=re.sub(r'\d+(?:\.\d+)?','#',item['text'])
    plain=re.sub('|'.join(map(re.escape,color_words)),'颜色',plain)
    plain=re.sub(r'[\s【】。，、；：]','',plain)
    if len(plain)>=20 and any(difflib.SequenceMatcher(None,plain,other).ratio()>.84 for other in normalized):raise ValueError('repetitive item wording')
    normalized.append(plain)
   for key in ('opening','closing'):
    if re.search(r'不推荐|候选|硬凑|已保留|不符合|其他.{0,8}(?:不好|不适合)',draft.get(key,'')):raise ValueError('negative intro')
    if any(n not in set(re.findall(r'\d+(?:\.\d+)?',all_facts)) for n in re.findall(r'\d+(?:\.\d+)?',draft.get(key,''))):raise ValueError('new intro numbers')
   # Stable factual opening keeps the winner and comparison arithmetic intact.
   draft['opening']=plan['opening'];draft['closing']=plan['closing']
   return draft,True
  except (ValueError,KeyError,TypeError,StopIteration):return plan,False
 def handle(self,d,deadline):
  text=d['text'].strip();history=d.get('history',[])
  history=[{'role':m['role'],'content':m['content'][:5000]} for m in history[-10:] if isinstance(m,dict) and m.get('role') in ('user','assistant') and isinstance(m.get('content'),str)] if isinstance(history,list) else []
  targets=self.ids(d.get('target_ids',[]));visible=self.ids(d.get('current_ids',[]));c=clean(d.get('conditions',{}))
  asked=[k for k in d.get('asked',[]) if k in FIELDS] if isinstance(d.get('asked'),list) else []
  skip=[k for k in d.get('skip',[]) if k in FIELDS] if isinstance(d.get('skip'),list) else []
  generic_entry=bool(re.fullmatch(r'(?:请)?(?:帮我)?(?:推荐|选)(?:一款|一个)(?:背包|双肩包)[。！!？?\s]*',text)) and not c and not targets
  restart=bool(re.search(r'重新开始|从头选|重新选一款背包',text))
  if d.get('start_selection') or generic_entry or restart:
   k,q,choices=followup({},[],[])
   return dict(reply='好呀，先说说平时怎么用，我再帮你挑。',intent='recommend',conditions={},primary_ids=[],backup_ids=[],pending_ids=[],ids=[],product_texts={},question=q,choices=choices,suggestions=[],asked=[k],skip=[],understanding_source='entry',wording_source='catalog')
  local=local_patch(text,c)
  action=d.get('action','auto')
  if targets and action in ('analysis','compare') and local['intent']!='recommend':
   patch=local;patch['intent']=action;source='selected-product'
  else:patch,source=self.interpret(text,c,history,targets,visible,deadline)
  intent=patch.get('intent','chat')
  if intent=='recommend':c=merge_state(c,patch)
  analysis_conditions=merge_state(c,local) if intent in ('analysis','compare') else c
  if intent=='recommend':skip=list(dict.fromkeys(skip+patch.get('skip',[])+patch.get('remove',[])))
  found=self.ids(patch.get('target_ids',[]))
  if found and not targets:targets=found
  if intent in ('analysis','compare') and not targets:targets=visible[:3]
  if intent=='compare' and len(targets)<2:raise ValueError('请先选择两款商品，或把想比较的商品带进聊天框。')
  if intent=='analysis' and not targets:raise ValueError('请先选择想问的商品，或在购物车中点“就这款提问”。')
  primary=[];backup=[];focused=[];q='';choices=[];kind=patch.get('question_kind') or kind_from_text(text)
  if kind=='general':kind=kind_from_text(text)
  if intent=='recommend':kind='general'
  if intent=='recommend':
   matches=search(self.goods,c)
   # A new batch keeps all hard conditions and rotates already seen choices when possible.
   if re.search(r'换一组|换几款|再来几款|其他款式',text):matches.sort(key=lambda p:(p['id'] in visible,-rank(p,c)))
   limit=1 if re.search(r'只(?:要|推荐|选).{0,2}一款|就要一款',text) else 5
   primary=matches[:limit];backup=matches[limit:limit+5];focused=primary+backup
   if not matches:
    choices=[]
    if c.get('budget') is not None:
     without={k:v for k,v in c.items() if k!='budget'}
     prices=[p['price'] for p in search(self.goods,without) if type(p.get('price')) in (int,float)]
     if prices:choices.append('预算提高到'+number(math.ceil(min(prices)/50)*50,'元'))
    for fields,label in [(('color','excluded_colors'),'取消颜色限制'),(('aesthetics','style'),'取消风格限制'),(('water_need','water'),'取消防水要求'),(('laptop',),'取消电脑尺寸限制')]:
     if any(f in c for f in fields) and search(self.goods,{k:v for k,v in c.items() if k not in fields}):choices.append(label)
    q='你愿意先调整哪一项？我再按你的选择找。'
    if not choices:choices=['重新选一款背包']
   else:
    k,q,choices=followup(c,asked,skip)
    if k:asked=list(dict.fromkeys(asked+[k]))
  elif intent in ('analysis','compare'):focused=[self.goods[i] for i in targets[:(1 if intent=='analysis' else 3)]]
  if intent=='chat':
   answer=self.completion([{'role':'system','content':'你是中文购物助手。自然直接回答当前问题，知识问题正常解释，不强行转回推荐商品，不提问。不虚构商品信息，不输出思考过程。'}]+history[-4:]+[{'role':'user','content':text}],deadline,False,1400)
   return dict(reply=answer.replace('**',''),intent=intent,conditions=c,ids=[],primary_ids=[],backup_ids=[],pending_ids=[],product_texts={},question='',choices=[],suggestions=[],asked=asked,skip=skip,understanding_source=source,wording_source='model')
  plan=blueprint(intent,focused,primary,backup,analysis_conditions,text,kind)
  # Read-only factual questions use exact facts instead of asking a model to recalculate.
  if source=='explicit-model-unavailable' or kind in ('weight','capacity','reviews','cons') and intent in ('analysis','compare'):draft,rewritten=plan,False
  else:
   if intent=='recommend' and backup:
    main_plan={**plan,'items':plan['items'][:len(primary)]}
    draft,rewritten=self.validated_wording(main_plan,primary,deadline)
    draft['items']=draft['items']+plan['items'][len(primary):]
   else:draft,rewritten=self.validated_wording(plan,focused,deadline)
  return dict(reply=(draft.get('opening','')+'\n'+draft.get('closing','')).strip().replace('**',''),product_texts={str(i['id']):i['text'].replace('**','') for i in draft['items']},intent=intent,conditions=c,primary_ids=[p['id'] for p in primary],backup_ids=[p['id'] for p in backup],pending_ids=[],ids=[p['id'] for p in focused] if intent in ('analysis','compare') else [],question=q,choices=choices,suggestions=suggestion_bank(intent,text,history),asked=asked,skip=skip,understanding_source=source,wording_source='model-grounded' if rewritten else 'catalog-grounded')
