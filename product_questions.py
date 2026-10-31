"""Question-first product facts. No shopping-state edits and no model-generated specs."""
import re

TOPIC_PATTERNS=[
 ('hand_carry',r'手提|拎着|拎起来|提着|提手|手拎'),
 ('waterproof',r'防水|防不防水|防泼|下雨|淋雨|湿(?:到|了|里面|内部)|进水'),
 ('strap_width',r'肩带.{0,3}(?:宽|款)|背带.{0,3}宽|宽肩带'),
 ('breathability',r'闷|透气|后背.{0,5}(?:热|汗)|夏天.{0,6}热|背.{0,5}很热'),
 ('shoulder_comfort',r'肩膀.{0,5}(?:疼|痛|酸)|肩带.{0,5}勒|勒肩|压肩|背久|背.{0,4}累|减压|不压肩'),
 ('spinal_support',r'护脊|脊柱|护背'),
 ('laptop',r'电脑|笔记本|\d+(?:\.\d+)?[寸吋]'),
 ('book_fit',r'书本|装书|课本|A4|a4'),
 ('umbrella_bottle',r'雨伞|折叠伞|伞和|水杯和|雨具'),
 ('side_bottle',r'侧边.{0,5}(?:水杯|杯子|水瓶)|侧(?:面|袋).{0,5}(?:杯|瓶)|水杯侧袋'),
 ('size',r'太小|很小|太大|很大|笨重|多大|尺寸|大小'),
 ('weight',r'多重|很重|会不会重|重不重|重量|轻不轻|背起来轻|轻便|多少克'),
 ('daily_capacity',r'日常.{0,6}(?:够|用)|出门.{0,5}够|够不够用'),
 ('trip_capacity',r'短途|一日游|两日游|出去玩.{0,5}装|出去玩'),
 ('cleaning',r'好不好擦|好擦|擦洗|清洗|清洁|怎么洗|能洗吗'),
 ('dirt',r'耐脏|容易脏|易脏|不容易脏|脏了'),
 ('durability',r'磨破|耐磨|耐用|结实|破不破|牢固|撕裂|做工'),
 ('pockets',r'口袋.{0,4}多|分区|隔层多|东西.{0,5}好.{0,2}找|好找|找东西|收纳'),
 ('hidden_pocket',r'隐藏口袋|暗袋|隐形口袋|隐藏袋'),
 ('theft',r'被偷|防盗|偷走|手机.{0,4}安全'),
 ('shape',r'软塌|塌塌|挺括|硬挺|支撑|版型|好不好看|好看吗'),
 ('style',r'老气|显老|搭衣服|好搭|百搭|穿搭'),
 ('commute',r'上班.{0,5}(?:合适|适合|可以|行吗)|通勤.{0,5}(?:合适|适合|可以)|适合上班'),
 ('school',r'上学.{0,5}(?:可以|行吗|合适|适合)|学生.{0,8}(?:可以|合适)|适合上学'),
 ('hiking',r'徒步|登山|爬山|露营'),
 ('shopping',r'逛街'),
 ('zipper',r'拉链|好不好拉|顺不顺|卡不卡'),
 ('luggage',r'行李箱|拉杆|套在箱'),
 ('charging',r'充电口|USB|usb|充电接口'),
 ('reflective',r'反光|夜间|晚上'),
]

COMMON_QUESTIONS=[
'背着会不会闷后背','背久了肩膀疼不疼','肩带会不会勒','背起来轻不压肩','有没有护脊','夏天背会不会很热','肩膀会不会酸','能不能装14寸电脑','够不够装书本','会不会太小','能不能装雨伞水杯','会不会很大很重','日常出门够不够用','短途出去玩能装东西吗','下雨会不会湿里面','好不好擦','容不容易磨破','结实不结实','布料耐不耐脏','口袋多不多','东西好不好找','有没有隐藏口袋','放手机会不会容易被偷','侧边能不能放水杯','有没有单独放电脑的地方','会不会软塌塌','版型好不好看','会不会很重','颜色耐不耐脏','会不会老气','好不好搭衣服','上班背合适吗','学生上学背可以吗','出去玩徒步能用吗','逛街背会不会笨重','拉链好不好拉','能不能套在行李箱拉杆上','有没有充电口','晚上有没有反光','这款防水吗','这款肩带款吗','这款可以手提吗']


def normalize(text):return re.sub(r'肩带款(?=吗|不|？|\?|$)','肩带宽',text)


def topics(text):
 t=normalize(text)
 found=[(m.start(),i,key) for i,(key,pattern) in enumerate(TOPIC_PATTERNS) for m in [re.search(pattern,t)] if m]
 out=[v[2] for v in sorted(found)]
 if 'side_bottle' in out and 'umbrella_bottle' in out and not re.search(r'伞',t):out.remove('umbrella_bottle')
 return out


def is_overview(text):return bool(re.fullmatch(r'\s*(?:请|帮我)?\s*分析(?:一下)?(?:商品)?\s*[「“\"].+[」”\"]\s*[。.!！]?\s*',text))


def asks_product_question(text):
 if is_overview(text):return False
 if re.search(r'推荐|帮我选|换一款|换个|找一款|想买',text):return False
 return bool(topics(text) and (re.search(r'吗|么|？|\?|会不会|能不能|有没有|是否|好不好|够不够|不不|多不多|太不|疼不疼|结实不结实|容不容易|重不重|轻不轻|多重|多少|多大|这款|这个|这一款|怎么样',text) or text in COMMON_QUESTIONS))


def num(value,suffix=''):
 return f'{value:g}{suffix}' if type(value) in (int,float) else '未提供'


def _answer(p,topic,text):
 a=p.get('attributes',{});flags=p.get('feature_flags',{});weight=p.get('weight');cap=p.get('capacity');width=p.get('shoulder_width_cm');wide=flags.get('宽肩带');category=p.get('categories',[])
 if topic=='hand_carry':
  mode=a.get('hand_carry_type')
  if mode=='双手提环':return '【可以手提】。这款有双手提环，也能双肩背，两种方式可以切换。'
  if mode=='长提带':return '【可以手提】。这款有长提带，也能单肩背，装重物时要注意手部负担。'
  if mode=='顶部提手':return '【可以短距离手提】。顶部有提手，拿起、上下车时方便；它主要用于双肩背，装满后不适合长时间拎着。'
  if mode=='无独立提手':return '【没有独立手提把手】，这款主要按肩背方式使用，不建议提着抽绳或拉链长期承重。'
  return '手提结构资料暂未提供，不能直接确认是否支持手提。'
 if topic=='waterproof':
  level=p.get('water_protection')
  if level=='防泼水':return '【只能防泼水，不是整包完全防水】。短时水滴可以应付，持续淋雨时水仍可能从拉链或缝线进入，里面的电脑和手机要额外防护。'
  if level=='日常防雨':return '【短时小雨可以应付】；持续大雨或浸水仍有进水风险，不能保证里面始终干燥。贵重物品建议加防水内袋。'
  if level=='有防水证明':return ('资料列有【'+p['water_test']+'】，' if p.get('water_test') else '资料标有防水证明，但缺少具体测试等级，')+'开口未闭合、长时间浸水仍可能进水，不能直接当作可以泡在水里的防水袋。'
  return '目前没有这款的防水等级资料，不能直接保证下雨不会湿到里面；需要到商品页核对面料、接缝和拉链的防水说明。'
 if topic=='strap_width':
  if width is None:return '肩带具体宽度暂未提供，需核对商品页的肩带尺寸。'
  return f'肩带宽【{num(width,"cm")}】，'+('属于宽肩带设计。' if wide else '属于偏窄的肩带。')+(f'肩部有{num(a.get("shoulder_padding_mm"),"mm")}加垫，宽度和加垫有助于分散接触压力。' if a.get('shoulder_padding_mm') else '肩部加垫较少，建议以轻装携带为主。')
 if topic=='breathability':
  if a.get('back_mesh') is True:return '有透气网布'+('和背部通风槽' if a.get('ventilation_channels') else '')+'，能减少整片背板贴住后背的感觉。'+('【夏天仍可能热、出汗】，不是有网布就完全不闷。' if re.search(r'夏天|热|汗',text) else '【不能保证完全不闷】，天气热、背得久或装得很满时仍可能出汗。')
  if a.get('back_mesh') is False:return '没有专门的透气网布背板，背部贴合较多时会更容易觉得闷，夏天长时间背需要留意出汗。'
  return '目前没有背板透气结构资料，无法只凭外观判断闷不闷；实际也会受温度、衣着和背负时间影响。'
 if topic=='shoulder_comfort':
  if width is None:return '不能直接保证久背不酸或不勒。肩带宽度和加垫资料尚不完整，负重、体型和调节方式都会影响肩部感受。'
  if wide:return f'{num(width,"cm")}宽肩带'+(f'配{num(a.get("shoulder_padding_mm"),"mm")}加垫' if a.get('shoulder_padding_mm') else '')+'，接触面积更大。'+f'但【不能保证背久了不酸、不勒】，装得重仍会压肩；这款建议日常负重约{a.get("comfort_load_kg","按实际背感调整")}kg，并调好左右肩带。'
  return f'这款肩带约{num(width,"cm")}，加垫较少，装重物或长时间背更可能有勒肩感。更适合轻装携带，不能保证久背肩膀不酸。'
 if topic=='spinal_support':
  if a.get('spinal_certification'):return '资料中列有护脊结构说明，但是否适合具体体型还要看尺码、负重与实际背负；不能把它当作治疗或矫正工具。'
  return ('有普通背板支撑，' if a.get('back_support') else '没有专门护脊背负结构，')+'但【没有专业护脊效果证明】。普通加垫或支撑板不等于能保护、矫正脊柱。'
 if topic=='laptop':
  target=re.search(r'(\d+(?:\.\d+)?)\s*(?:英寸|寸|吋)',text);requested=float(target.group(1)) if target else None
  if flags.get('电脑隔层') is not True or p.get('laptop') is None:return '【没有独立缓冲电脑隔层】。不能按电脑包保证尺寸适配，携带电脑时需额外内胆保护并先核对主仓尺寸。'
  maximum=p['laptop'];inside=a.get('laptop_compartment_cm')
  if requested is not None and requested>maximum:return f'这款标称适配上限是【{num(maximum,"英寸")}】，不能保证装下你的{num(requested,"英寸")}电脑。'
  lead=f'可以，标称支持{num(requested,"英寸")}电脑。' if requested is not None else '有，电脑有单独的收纳隔层。'
  return lead+('隔层有加厚缓冲。' if p.get('computer_padding')=='air' else '隔层为基础缓冲。')+(f'内仓约{inside[0]}×{inside[1]}×{inside[2]}cm，购买前请和电脑外壳尺寸核对。' if inside else f'标称适配{num(maximum,"英寸")}，仍需核对电脑外壳与内仓尺寸。')
 if topic=='book_fit':
  if a.get('a4_book_fit') is True:return f'【可以装A4大小书本】。主仓适合约{a.get("book_load_example","常规课本和文具")}，厚书数量会受厚度、电脑和水杯占用的空间影响。'
  if a.get('a4_book_fit') is False:return '这款主仓不适合平整放A4大小书本，主要用于随身小物；小开本书也要先核对尺寸。'
  return '还缺主仓内部尺寸，不能只凭容量保证书本能平整放下；请核对书本长宽与主仓开口。'
 if topic=='umbrella_bottle':
  umbrella=a.get('folded_umbrella_max_cm');parts=[]
  if umbrella:parts.append(f'主仓可放折叠后长度不超过约{num(umbrella,"cm")}的雨伞。')
  else:parts.append('折叠伞是否能放下还需要核对主仓尺寸。')
  if flags.get('水杯侧袋'):parts.append(f'有水杯侧袋，适合直径约{num(a.get("bottle_diameter_cm"),"cm")}以内的杯子；超大杯还要核对杯身。')
  else:parts.append('没有水杯侧袋，密封好的杯子只能结合主仓空间安排，避免漏水碰到书本或电脑。')
  return ''.join(parts)
 if topic=='side_bottle':
  if flags.get('水杯侧袋') is True:return f'有侧边水杯袋，开口适合直径约【{num(a.get("bottle_diameter_cm"),"cm")}】以内的杯子，放入后还要确认杯身稳定。'
  if flags.get('水杯侧袋') is False:return '【没有专门的水杯侧袋】。如果放主仓，先确认杯盖密封，并和电脑、书本隔开放。'
  return '侧袋结构资料未提供，需在商品页核对是否有水杯袋及开口尺寸。'
 if topic=='size':
  scale='偏小，主要装随身小物' if cap is not None and cap<12 else '偏轻巧的日常体量' if cap is not None and cap<20 else '常规日常体量' if cap is not None and cap<=26 else '偏大，装物余地较多'
  return f'容量【{num(cap,"L")}】，外形约{p.get("dimensions") or "尺寸未提供"}，属于{scale}。'+('如果还要塞厚衣物或很多厚书，需要先核对主仓余量。' if cap is not None and cap<=26 else '日常逛街可能更占空间，是否显大也和身高、体型有关。')
 if topic=='weight':
  scale='空包偏轻' if weight is not None and weight<=450 else '常规重量' if weight is not None and weight<=700 else '空包偏重'
  return f'【空包{num(weight,"g")}】，属于{scale}。装入书本、电脑和水杯后的总重量会增加，轻包也不能保证一定不压肩。'
 if topic=='daily_capacity':
  if cap is not None and cap>=15:return f'日常出门通常够用，{num(cap,"L")}主仓可以安排随身物品。'+('不过这款体量偏大，更适合东西较多时使用。' if cap>26 else '如果主要是钱包、手机、水杯和薄外套，收纳比较从容。')
  return f'轻装出门够用，{num(cap,"L")}主要放手机、钱包、钥匙等小物；书本或较多衣物要先核对主仓。'
 if topic=='trip_capacity':
  if cap is not None and cap>=25:return f'{num(cap,"L")}容量适合轻装短途出行，可安排少量换洗衣物和随身用品。厚外套、鞋子或多天行李会明显占空间，不能只按升数保证全部装下。'
  if cap is not None and cap>=15:return f'一日游轻装通常够用，{num(cap,"L")}适合水杯、折叠伞、薄外套和小物；过夜换洗衣物较多时会紧一些。'
  return f'{num(cap,"L")}只适合短途随身小物，不适合作为装换洗衣物的主要行李。'
 if topic=='cleaning':return a.get('cleaning_note') or '清洁方式资料未提供，先核对洗护标签；不要默认可以机洗或整包浸泡。'
 if topic=='dirt':return a.get('dirt_note') or '目前没有耐污或清洁测试资料，不能保证不显脏；颜色深浅与面料表面都会影响污渍是否明显。'
 if topic=='durability':return a.get('durability_note') or '目前没有受力加固或耐磨资料，不能只看外观保证结实。需要核对面料、车线与建议负重。'
 if topic=='pockets':
  count=a.get('pocket_count');simple=flags.get('少分区')
  return (f'共约【{count}个收纳位置】，' if count is not None else '')+('分区偏简单，常用物品集中放，拿取路径直接。' if simple else '分区相对多，电脑、配件和小物可以分开放；固定每类物品的位置会更好找。')
 if topic=='hidden_pocket':
  value=flags.get('防盗口袋')
  return '有贴身拉链暗袋，可以放手机或证件；暗袋不等于带锁的防盗装置。' if value is True else '没有标注独立隐藏口袋，不能把普通前袋当作暗袋。' if value is False else '目前没有隐藏口袋资料，需要看商品页的袋位结构。'
 if topic=='theft':return ('有贴身拉链暗袋，手机放里面并拉好拉链，能减少随手取物的风险。' if flags.get('防盗口袋') else '没有独立贴身暗袋，手机尽量放靠近身体的内袋并拉好拉链。')+'【不能保证防偷或防割】，人多时仍需留意。'
 if topic=='shape':return a.get('shape_note') or p.get('design_note') or '包型支撑资料未提供，是否软塌需要看空包与装载后的对照。'
 if topic=='style':
  design=p.get('design_note','');style='、'.join(p.get('aesthetic_tags',[]))
  return f'整体偏【{style or "日常休闲"}】，{design}。'+('复古细节会显得成熟一些，是否老气还要看整体穿搭和个人喜好。' if '复古' in p.get('aesthetic_tags',[]) else '搭配简单的上衣、裤装比较直接，好不好看也取决于个人审美。')
 if topic=='commute':
  if '通勤' in p.get('scene',[]):return '上班通勤可以用，'+(f'有标称{num(p["laptop"],"英寸")}电脑隔层，' if p.get('laptop') else '')+f'空包{num(weight,"g")}。如果每天带电脑，还要核对实际外壳和内仓尺寸。'
  return f'可以携带日常物品，但这款的定位偏{"户外装备" if "户外登山包" in category else "轻装随身"}，空包{num(weight,"g")}；是否适合上班，要结合电脑和文件的尺寸。'
 if topic=='school':return _answer(p,'book_fit',text)+f'空包{num(weight,"g")}，还要给水杯、文具留出位置。'
 if topic=='hiking':
  if '户外登山包' in category:return f'可以用于轻徒步，{num(cap,"L")}容量，'+('有胸扣等背负固定结构。' if flags.get('胸扣') else '要按实际负重调好背带。')+'具体负重和雨天防护仍需按资料范围使用。'
  return '轻装短途步行可以，但这款是日常包型，'+('没有专门的胸扣、腰带等重装背负结构，' if not flags.get('胸扣') else '')+'不能按专业重装登山包的用途保证承载与稳定性。'
 if topic=='shopping':return (f'逛街轻装比较方便，空包{num(weight,"g")}、{num(cap,"L")}。' if weight is not None and weight<=500 and cap is not None and cap<=25 else f'这款{num(cap,"L")}、空包{num(weight,"g")}，逛街时会更占空间或增加自重。')+'装满后的体积和重量也会影响携带感。'
 if topic=='zipper':return a.get('zipper_note') or '拉链形式与开合资料尚未提供，不能直接保证顺滑；需看商品页细节及实际评价。'
 if topic=='luggage':
  if flags.get('行李箱插带') is True:return '【可以套在行李箱拉杆上】，背部有拉杆插带。使用前确认带宽与拉杆匹配，拉杆晃动时仍需扶稳。'
  return '没有专门的行李箱拉杆插带，不能保证能稳固套在拉杆上。' if flags.get('行李箱插带') is False else '拉杆插带资料未提供，需要核对背部结构。'
 if topic=='charging':return '有外接充电接口，但包本身不供电，需要自备充电宝和线材，也不是防水充电装置。' if a.get('charging_port') is True else '【没有外接充电口】。可以自行携带充电宝，但不要把普通走线孔当作充电功能。' if a.get('charging_port') is False else '是否有充电接口尚无资料，不能直接确认。'
 if topic=='reflective':return '有反光细节，在外部光线照射下可以反射；它不是主动照明，也不能保证夜间安全。' if a.get('reflective_details') is True else '【没有标注专门的反光设计】，晚上使用不要依赖包体提升可见度。' if a.get('reflective_details') is False else '反光结构资料未提供，需核对商品页细节。'
 return ''


def answer(p,text):
 selected=topics(text)
 if not selected:return None
 return '\n'.join(_answer(p,topic,normalize(text)) for topic in selected)
