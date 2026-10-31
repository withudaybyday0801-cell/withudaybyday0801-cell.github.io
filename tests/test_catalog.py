"""64-SKU and 25-language-case offline acceptance. No training / real-model claim."""
import sys,json,threading,unittest,urllib.request,urllib.error,time,contextlib,io
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bag_engine as be
import bag_local as app
CASES=json.loads((ROOT/'tests/acceptance_cases.json').read_text())

class ExplicitEngine(be.Engine):
 """Exercise the actual explicit interpreter, matcher and answer builder, not a fake NLU."""
 def interpret(self,text,c,history,targets,visible,deadline):return be.local_patch(text,c),'explicit-offline'
 def validated_wording(self,plan,context,deadline):return plan,False

class CatalogTests(unittest.TestCase):
 def test_identity_and_images(self):
  self.assertGreaterEqual(len(app.GOODS),50)
  for key in ('id','sku','family','name'):self.assertEqual(len({p[key] for p in app.GOODS}),len(app.GOODS),key)
  self.assertEqual(len({(p['photo_sheet'],p['photo']) for p in app.GOODS}),len(app.GOODS))
 def test_full_records(self):
  for p in app.GOODS:
   with self.subTest(sku=p['sku']):
    for key in ('weight','capacity','dimensions','material','rating','review_count','sales','reviews','shop_name','service_tags','sku'):self.assertTrue(p.get(key),key)
    self.assertEqual(p['feature_flags']['电脑隔层'],p['laptop'] is not None)
    self.assertFalse(any(x in ';'.join(p['limits']) for x in ('未显示','原型')))
 def test_25_original_prompts(self):
  engine=ExplicitEngine(app.GOODS,None);state={};asked=[];skip=[];history=[];group=None;report=[]
  for case in CASES:
   if case['group']!=group:state={};asked=[];skip=[];history=[];group=case['group']
   with self.subTest(id=case['id'],text=case['text']):
    body=dict(text=case['text'],conditions=state,history=history,asked=asked,skip=skip,action=case.get('action','auto'),target_ids=case.get('target_ids',[]))
    result=engine.handle(body,time.monotonic()+100)
    for field,value in case['expected_conditions'].items():self.assertEqual(result['conditions'].get(field),value,field)
    for field in case['absent_conditions']:self.assertNotIn(field,result['conditions'])
    if case['expected_primary_count'] is not None:self.assertEqual(len(result['primary_ids']),case['expected_primary_count'])
    for id in result['primary_ids']+result['backup_ids']:self.assertTrue(be.match(app.GOODS[id],result['conditions'])[0])
    if result['intent']=='recommend':
     texts=result['reply']+' '.join(result['product_texts'].values());self.assertNotRegex(texts,r'不推荐|淘汰|硬凑|其他.*不好|截图呈现|保留条件')
    if case['id']==1:self.assertTrue(result['question']);self.assertEqual(result['primary_ids'],[])
    if case['id']>=21:self.assertFalse(result['question'])
    if case['id']==21:self.assertIn('510g',result['product_texts']['2']);self.assertIn('21L',result['product_texts']['2'])
    if case['id']==22:self.assertIn(app.GOODS[2]['limits'][0],result['product_texts']['2'])
    if case['id']==23:self.assertIn(str(app.GOODS[2]['rating']),result['product_texts']['2']);self.assertIn('评价里提到',result['product_texts']['2'])
    if case['id']==25:self.assertIn('214g',result['reply']);self.assertIn('296g',result['product_texts']['1']);self.assertIn('510g',result['product_texts']['2'])
    report.append(dict(id=case['id'],text=case['text'],conditions=result['conditions'],primary_ids=result['primary_ids'],reply=result['reply'],product_texts=result['product_texts'],status='passed',scope='offline-explicit-logic-and-catalog'))
    state=result['conditions'];asked=result['asked'];skip=result['skip'];history +=[{'role':'user','content':case['text']},{'role':'assistant','content':result['reply']}]
  Path('/tmp/baodongni-25-offline-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 def test_cancellations_remove_related_state(self):
  original=dict(color='蓝色',excluded_colors=['粉色'],budget=200,laptop=16,needs_laptop=True,protection='air',features=['电脑隔层','宽肩带'],water_need='日常防雨',water=True,aesthetics=['极简'],style='简约',maxweight=450,priority='轻便')
  cases=[('颜色不限',('color','excluded_colors')),('预算不限',('budget',)),('不带电脑了',('laptop','needs_laptop','protection')),('不需要防水了',('water','water_need')),('重量不用管了',('maxweight','priority')),('取消风格限制',('style','aesthetics'))]
  for text,absent in cases:
   c=be.merge_state(original,be.local_patch(text,original))
   for field in absent:self.assertNotIn(field,c,text)
  c=be.merge_state(original,be.local_patch('不需要宽肩带了',original));self.assertEqual(c['features'],['电脑隔层'])
  c=be.merge_state(original,be.local_patch('不要简约风了',original));self.assertNotIn('style',c);self.assertNotIn('aesthetics',c)
 def test_remove_only_requested_condition(self):
  old=dict(needs_laptop=True,laptop=16,budget=200,color='蓝色',features=['电脑隔层','宽肩带'])
  result=be.merge_state(old,be.local_patch('取消电脑尺寸限制',old))
  self.assertNotIn('laptop',result);self.assertTrue(result['needs_laptop']);self.assertEqual(result['features'],old['features'])
  self.assertEqual(result['budget'],200);self.assertEqual(result['color'],'蓝色')
  result=be.merge_state(old,be.local_patch('不要蓝色这个条件了',old));self.assertNotIn('color',result);self.assertFalse(result.get('excluded_colors'))
 def test_analysis_does_not_change_shopping_conditions(self):
  e=ExplicitEngine(app.GOODS,None);before={'budget':200,'color':'蓝色'}
  answer=e.handle({'text':'这款能装16英寸电脑吗','action':'analysis','target_ids':[2],'conditions':before},time.monotonic()+20)
  self.assertEqual(answer['conditions'],before);self.assertIn('16英寸',answer['product_texts']['2'])
 def test_no_match_does_not_relax_automatically(self):
  e=ExplicitEngine(app.GOODS,None);text='预算50元以内，要装16英寸电脑，还要适合长时间淋雨。'
  result=e.handle({'text':text},time.monotonic()+10)
  self.assertEqual(result['conditions']['budget'],50);self.assertEqual(result['primary_ids'],[])
  self.assertEqual(result['choices'],['预算提高到350元'])
  new=be.merge_state(result['conditions'],be.local_patch(result['choices'][0],result['conditions']))
  self.assertTrue(be.search(app.GOODS,new))
 def test_product_crop_metadata_and_long_titles(self):
  for p in app.GOODS:
   x,y,w,h=p['image_crop'];self.assertTrue(0<=x<x+w<=1024);self.assertTrue(0<=y<y+h<=1536)
   self.assertGreaterEqual(len(p['display_title']),22)
   self.assertTrue(p['display_title'].startswith(p['brand']))
  self.assertNotEqual(app.GOODS[31]['image_crop'][1],512)
 def test_recommendation_angles_differ(self):
  c={'needs_laptop':True,'laptop':16,'scene':'通勤'};products=be.search(app.GOODS,c)[:5]
  items=be.recommendation_items(products,c)
  self.assertEqual(len({i['focus'] for i in items}),5)
  self.assertEqual(len({i['text'].split('。')[0] for i in items}),5)
 def test_daily_scenes_never_recommend_technical_hiking(self):
  engine=ExplicitEngine(app.GOODS,None)
  for text in ['上课和校园日常','日常用','平时用的','上学用的','不登山，只上课','没有登山需求，只要日常背','上班通勤','周末逛街','酷酷的机能风，日常用']:
   with self.subTest(text=text):
    result=engine.handle({'text':text},time.monotonic()+10)
    self.assertIn(result['conditions']['scene'],('校园','通勤','休闲'))
    self.assertEqual(len(result['primary_ids']),5)
    all_ids=result['primary_ids']+result['backup_ids']+[p['id'] for p in be.search(app.GOODS,result['conditions'])]
    self.assertTrue(all('户外登山包' not in app.GOODS[i]['categories'] for i in all_ids))
 def test_scene_metadata_is_not_reputation_override(self):
  bad={**app.GOODS[38],'scene':['校园','通勤','休闲'],'rating':100,'sales':999999}
  for scene in ['校园','通勤','休闲']:
   self.assertFalse(be.match(bad,{'scene':scene})[0])
   self.assertNotIn(bad,be.search([bad]+[app.GOODS[22]],{'scene':scene}))
  for product in app.GOODS:
   if '户外登山包' in product['categories']:self.assertTrue(set(product['scene']).isdisjoint(be.DAILY_SCENES))
 def test_explicit_outdoor_remains_available(self):
  for text in ['周末去徒步','登山露营用','我去爬山用']:
   c=be.merge_state({},be.local_patch(text));self.assertEqual(c['category'],'户外登山包')
   results=be.search(app.GOODS,c);self.assertGreaterEqual(len(results),5)
   self.assertTrue(all('户外登山包' in p['categories'] for p in results))
 def test_switch_outdoor_to_daily_removes_old_category(self):
  current={'category':'户外登山包','scene':'旅行','budget':300}
  for text in ['上课和校园日常','上学用的','不去登山了，改成日常用','不登山，只上课','不要登山包，平时背的']:
   c=be.merge_state(current,be.local_patch(text,current));self.assertNotIn('category',c)
   self.assertEqual(c['budget'],300);self.assertIn(c['scene'],be.DAILY_SCENES)
   self.assertTrue(all('户外登山包' not in p['categories'] for p in be.search(app.GOODS,c)))
 def test_avoid_invented_hard_weight(self):
  self.assertNotIn('maxweight',be.local_patch('我想轻便一点')['updates'])
  self.assertNotIn('budget',be.local_patch('不超过450克')['updates'])
  patch=be.combine_patches({'intent':'recommend','updates':{'color':'蓝色','budget':200},'remove':[]},be.local_patch('预算不限',{'budget':200}))
  self.assertNotIn('budget',be.merge_state({'budget':200},patch))
 def test_water_levels_and_default_bag_type(self):
  rain=be.search(app.GOODS,{'water_need':'防泼水','category':'户外登山包'});self.assertTrue(any(p['water_protection']=='有防水证明' for p in rain))
  self.assertTrue(all('托特包' not in p['categories'] and '胸包' not in p['categories'] for p in be.search(app.GOODS,{})))

class ModelBoundaryTests(unittest.TestCase):
 def test_wrong_product_or_weight_rejected(self):
  p=app.GOODS[2];plan=be.blueprint('recommend',[p],[p],[],{},'推荐')
  for item in ({'id':1,'text':'错商品。'},{'id':2,'text':'空包999g。'},{'id':2,'text':'空包133.38g。'},{'id':2,'text':'蓝色背包。'},{'id':2,'text':'完全防水，能长时间淋雨。'}):
   e=be.Engine(app.GOODS,lambda *a,**kw:json.dumps({'opening':'','items':[item],'closing':''},ensure_ascii=False));result,accepted=e.validated_wording(plan,[p],time.monotonic()+30);self.assertFalse(accepted);self.assertEqual(result,plan)
 def test_correct_wording_accepted(self):
  p=app.GOODS[2];plan=be.blueprint('recommend',[p],[p],[],{},'推荐')
  draft={'opening':'日常上课可以看看这款。','items':[{'id':2,'text':'空包510g，21L容量，14英寸电脑有独立隔层。'}],'closing':''}
  e=be.Engine(app.GOODS,lambda *a,**kw:json.dumps(draft,ensure_ascii=False));self.assertTrue(e.validated_wording(plan,[p],time.monotonic()+30)[1])
 def test_model_stale_removal_guard(self):
  e=be.Engine(app.GOODS,lambda *a,**kw:json.dumps({'intent':'recommend','updates':{'budget':200,'color':'蓝色'},'remove':[]}))
  patch,_=e.interpret('预算不限',{'budget':200},[],[],[],time.monotonic()+30);self.assertNotIn('budget',be.merge_state({'budget':200},patch))
 def test_known_request_model_outage_keeps_data_grounded(self):
  def unavailable(*args,**kwargs):raise app.ProviderError('test unavailable',502)
  e=be.Engine(app.GOODS,unavailable);x=e.handle({'text':'推荐几款蓝色的背包'},time.monotonic()+5)
  self.assertEqual(len(x['primary_ids']),5);self.assertEqual(x['wording_source'],'catalog-grounded')
  self.assertTrue(all(app.GOODS[i]['color']=='蓝色' for i in x['primary_ids']))
 def test_invalid_key_not_disguised_as_model_success(self):
  def unauthorized(*args,**kwargs):raise app.ProviderError('test unauthorized',401)
  with self.assertRaises(app.ProviderError):be.Engine(app.GOODS,unauthorized).handle({'text':'推荐蓝色背包'},time.monotonic()+5)
 def test_repetitive_model_text_rejected(self):
  products=[app.GOODS[22],app.GOODS[46]];plan=be.blueprint('recommend',products,products,[],{},'推荐')
  texts=[f'这款空包{p["weight"]}g，容量{p["capacity"]}L，日常上课通勤都很方便。' for p in products]
  draft={'opening':'','items':[{'id':p['id'],'text':text} for p,text in zip(products,texts)],'closing':''}
  engine=be.Engine(app.GOODS,lambda *a,**kw:json.dumps(draft,ensure_ascii=False))
  self.assertFalse(engine.validated_wording(plan,products,time.monotonic()+20)[1])
 def test_upstream_preserves_auth_status(self):
  error=urllib.error.HTTPError('https://api.deepseek.com/chat/completions',401,'unauthorized',{},None)
  with patch.object(app.urllib.request,'urlopen',side_effect=error):
   with self.assertRaises(app.ProviderError) as failure:app.upstream('https://api.deepseek.com/chat/completions','test-only',b'{}')
   self.assertEqual(failure.exception.status,401)
 def test_daily_answer_rejects_model_inferred_outdoor_category(self):
  def stale(*a,**kw):return json.dumps({'intent':'recommend','updates':{'category':'户外登山包','scene':'旅行'},'remove':[]})
  engine=be.Engine(app.GOODS,stale);p,_=engine.interpret('上课和校园日常',{},[],[],[],time.monotonic()+10)
  c=be.merge_state({},p);self.assertEqual(c['scene'],'校园');self.assertNotEqual(c.get('category'),'户外登山包')
  self.assertTrue(all('户外登山包' not in g['categories'] for g in be.search(app.GOODS,c)))
 def test_model_cannot_sell_campus_bag_as_hiking_gear(self):
  p=app.GOODS[22];plan=be.blueprint('recommend',[p],[p],[],{'scene':'校园'},'上课用')
  draft={'opening':'','items':[{'id':p['id'],'text':'空包390g，适合徒步登山携带装备。'}],'closing':''}
  engine=be.Engine(app.GOODS,lambda *a,**kw:json.dumps(draft,ensure_ascii=False))
  self.assertFalse(engine.validated_wording(plan,[p],time.monotonic()+10)[1])
 def test_empty_body_retry(self):
  replies=[{'choices':[{'message':{'content':'','reasoning_content':'hidden'},'finish_reason':'stop'}]}, {'choices':[{'message':{'content':[{'type':'text','text':'直接回答。'}]},'finish_reason':'stop'}]}]
  with patch.object(app,'upstream',side_effect=replies) as upstream,contextlib.redirect_stdout(io.StringIO()):self.assertEqual(app.completion([],time.monotonic()+30),'直接回答。');self.assertEqual(upstream.call_count,2)

class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.App);threading.Thread(target=cls.server.serve_forever,daemon=True).start();cls.base=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def post(self,body,origin=None):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  with urllib.request.urlopen(urllib.request.Request(self.base+'/api/chat',data=json.dumps(body).encode(),headers=headers)) as r:return json.load(r)
 def test_catalog_and_all_photo_sheets(self):
  with urllib.request.urlopen(self.base+'/api/init') as r:self.assertEqual(len(json.load(r)['goods']),64)
  for i in range(3):
   with urllib.request.urlopen(self.base+f'/api/photo?sheet={i}') as r:self.assertTrue(r.read().startswith(b'\x89PNG'))
  with urllib.request.urlopen(self.base+'/?product=2') as r:self.assertEqual(r.status,200)
 def test_25_cases_through_http(self):
  engine=ExplicitEngine(app.GOODS,None);group=None;state={};asked=[];skip=[]
  with patch.object(app,'KEY','offline-test'),patch.object(app,'ENGINE',engine):
   for case in CASES:
    if case['group']!=group:state={};asked=[];skip=[];group=case['group']
    x=self.post(dict(text=case['text'],conditions=state,asked=asked,skip=skip,action=case.get('action','auto'),target_ids=case.get('target_ids',[])))
    for k,v in case['expected_conditions'].items():self.assertEqual(x['conditions'].get(k),v,case['text'])
    for k in case['absent_conditions']:self.assertNotIn(k,x['conditions'])
    state=x['conditions'];asked=x['asked'];skip=x['skip']
 def test_production_adapter_all_25_with_unhelpful_model(self):
  def unhelpful(messages,*args,**kwargs):
   return json.dumps({'intent':'chat','updates':{},'target_ids':[],'items':[],'opening':'','closing':''})
  state={};asked=[];skip=[];group=None
  with patch.object(app,'KEY','offline-test'),patch.object(app,'completion',side_effect=unhelpful):
   for case in CASES:
    if case['group']!=group:state={};asked=[];skip=[];group=case['group']
    x=self.post(dict(text=case['text'],conditions=state,asked=asked,skip=skip,action=case.get('action','auto'),target_ids=case.get('target_ids',[])))
    for k,v in case['expected_conditions'].items():self.assertEqual(x['conditions'].get(k),v,case['text'])
    for k in case['absent_conditions']:self.assertNotIn(k,x['conditions'])
    if case['expected_primary_count'] is not None:self.assertEqual(len(x['primary_ids']),case['expected_primary_count'],case['text'])
    state=x['conditions'];asked=x['asked'];skip=x['skip']
 def test_more_matches_uses_exact_same_filter_without_model(self):
  cases=[{'color':'蓝色','budget':200,'laptop':16,'aesthetics':['极简']},{'color':'黑色','budget':200,'maxweight':450},{'features':['宽肩带'],'water_need':'日常防雨'},{'color':'蓝色','excluded_colors':['粉色'],'scene':'校园'}]
  with patch.object(app,'KEY',''),patch.object(app,'completion') as model:
   for c in cases:
    req=urllib.request.Request(self.base+'/api/matches',data=json.dumps({'conditions':c}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as response:x=json.load(response)
    self.assertEqual(x['ids'],[p['id'] for p in be.search(app.GOODS,c)])
    self.assertTrue(all(be.match(app.GOODS[i],c)[0] for i in x['ids']))
   model.assert_not_called()
 def test_auth_and_validation(self):
  with patch.object(app,'KEY',''):
   with self.assertRaises(urllib.error.HTTPError):self.post({'text':'你好'})
  with patch.object(app,'KEY','offline-test'):
   with self.assertRaises(urllib.error.HTTPError) as e:self.post({'text':'你好'},'https://example.org')
   self.assertEqual(e.exception.code,403)
   with self.assertRaises(urllib.error.HTTPError):self.post({'text':''})

if __name__=='__main__':unittest.main()
