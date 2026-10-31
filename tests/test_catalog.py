"""Offline catalog and HTTP regression checks. No actual model calls or API key."""
import sys,json,threading,unittest,urllib.request,urllib.error,time,contextlib,io
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bag_local as app

class CatalogTests(unittest.TestCase):
 def test_identity_and_images(self):
  self.assertEqual(len(app.GOODS),22)
  for key in ('id','sku','photo','family'):
   self.assertEqual(len({p[key] for p in app.GOODS}),22,key)
 def test_full_consistent_simulation(self):
  for p in app.GOODS:
   with self.subTest(sku=p['sku']):
    for key in ('weight','capacity','dimensions','material','rating','review_count','sales','reviews','shop_name','service_tags','sku'):
     self.assertTrue(p.get(key),key)
    self.assertEqual(app.answer_product(p)['weight'],p['weight'])
    self.assertEqual(app.answer_product(p)['reviews'],p['reviews'])
    self.assertFalse(any(x in ';'.join(p['limits']) for x in ('未显示','未提供','原型')))
    self.assertTrue(90<=p['rating']<=100)
    self.assertEqual(p['feature_flags']['电脑隔层'],p['laptop'] is not None)
    self.assertTrue(all(isinstance(r,dict) and 'text' in r for r in p['reviews']))
 def test_colors_and_aesthetics(self):
  for query in ('推荐蓝色的背包','换成浅蓝色','我想要藏蓝的背包'):
   c=app.explicit_preferences(query,{},{});self.assertEqual(c['color'],'蓝色')
   primary,_,_=app.choose(c);self.assertGreaterEqual(len(primary),3)
   self.assertTrue(all(p['color']=='蓝色' for p in primary))
  self.assertEqual(app.conditions_clean({'color':'浅蓝色'})['color'],'蓝色')
  self.assertEqual(app.explicit_color('不要蓝色，要黑色'),'黑色')
  for style in ('清新少女','酷感机能','极简'):
   primary,_,_=app.choose({'aesthetics':[style]});self.assertTrue(primary)
   self.assertTrue(all(style in p['aesthetic_tags'] for p in primary))
 def test_function_constraints(self):
  for cond in ({'features':['宽肩带']},{'budget':150},{'water_need':'日常防雨'},{'laptop':16}):
   primary,_,_=app.choose(cond);self.assertTrue(primary)
   self.assertTrue(all(app.evaluate(p,cond)[0] for p in primary))
 def test_text_and_suggestions(self):
  result,notes=app.split_products('结论。[[商品:1]]轻便。[[商品:2]]简洁。',[app.GOODS[1],app.GOODS[2]])
  self.assertEqual(notes,{'1':'轻便。','2':'简洁。'})
  q='这款主要的缺点是什么';self.assertNotIn(q,app.related_questions('analysis',q,[]))
  self.assertNotIn('**',app.plain_reply('**结论**。','analysis'))

class ModelResponseTests(unittest.TestCase):
 def test_empty_body_retry(self):
  replies=[{'choices':[{'message':{'content':'','reasoning_content':'hidden'},'finish_reason':'stop'}]}, {'choices':[{'message':{'content':[{'type':'text','text':'直接回答。'}]},'finish_reason':'stop'}]}]
  with patch.object(app,'upstream',side_effect=replies) as upstream,contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(app.completion([],time.monotonic()+30),'直接回答。')
   self.assertEqual(upstream.call_count,2)
 def test_empty_retry_bounded(self):
  empty={'choices':[{'message':{'content':''},'finish_reason':'stop'}]}
  with patch.object(app,'upstream',return_value=empty) as upstream,contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaises(app.ProviderError):app.completion([],time.monotonic()+30)
   self.assertEqual(upstream.call_count,2)
 def test_json_repair(self):
  with patch.object(app,'completion',side_effect=['{bad json',json.dumps({'intent':'recommend','changes':{'color':'蓝色'},'target_ids':[],'skip':[]})]):
   self.assertEqual(app.extract('蓝色',{},[],[],[],time.monotonic()+30)['changes']['color'],'蓝色')

class HttpTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.App)
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.base=f'http://127.0.0.1:{cls.server.server_port}'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
 def post(self,body,origin=None):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  req=urllib.request.Request(self.base+'/api/chat',data=json.dumps(body).encode(),headers=headers)
  with urllib.request.urlopen(req) as r:return json.load(r)
 def test_init_and_photo(self):
  with urllib.request.urlopen(self.base+'/api/init') as r:self.assertEqual(len(json.load(r)['goods']),22)
  with urllib.request.urlopen(self.base+'/api/photo') as r:self.assertEqual(r.headers['Content-Type'],'image/png');self.assertTrue(r.read().startswith(b'\x89PNG'))
 def test_product_deep_link(self):
  with urllib.request.urlopen(self.base+'/?product=2') as r:
   self.assertEqual(r.status,200);self.assertIn('text/html',r.headers['Content-Type'])
 def test_start_selection_no_model_call(self):
  with patch.object(app,'KEY','test-only'),patch.object(app,'completion') as model:
   x=self.post({'text':'请帮我推荐一款背包','action':'recommend','start_selection':True})
   model.assert_not_called();self.assertTrue(x['question']);self.assertEqual(x['primary_ids'],[])
 def test_blue_overrides_extractor_omission(self):
  def fake(messages,deadline,json_mode=False,max_tokens=2200):
   if json_mode:return json.dumps({'intent':'analysis','changes':{},'target_ids':[1,2],'skip':[]})
   context=json.loads(messages[1]['content']);self.assertTrue(all(p['color']=='蓝色' for p in context['products']))
   return '先看浅蓝色这款，平时上课背比较好搭。'
  with patch.object(app,'KEY','test-only'),patch.object(app,'completion',side_effect=fake):
   x=self.post({'text':'推荐几款蓝色的背包','action':'auto','current_ids':[1,2]})
   self.assertEqual(x['intent'],'recommend');self.assertEqual(x['conditions']['color'],'蓝色')
   self.assertTrue(all(app.GOODS[i]['color']=='蓝色' for i in x['primary_ids']))
 def test_compare_and_analysis_current_data(self):
  for action,ids in [('analysis',[2]),('compare',[1,2])]:
   def fake(messages,*args,**kwargs):
    context=json.loads(messages[1]['content'])
    for p in context['products']:
     self.assertEqual(p['weight'],app.GOODS[p['id']]['weight']);self.assertTrue(p['reviews']);self.assertTrue(p['rating'])
    return '[[商品:2]]空包510g，电脑隔层缓冲一般。'
   with patch.object(app,'KEY','test-only'),patch.object(app,'completion',side_effect=fake):
    x=self.post({'text':'主要缺点是什么','action':action,'target_ids':ids})
    self.assertEqual(x['ids'],ids);self.assertFalse(x['question'])
 def test_auth_and_input_errors(self):
  with patch.object(app,'KEY',''):
   with self.assertRaises(urllib.error.HTTPError) as e:self.post({'text':'你好'})
   self.assertEqual(e.exception.code,400)
  with patch.object(app,'KEY','test-only'):
   for data in ({'text':''},{'text':'比较','action':'compare','target_ids':[1]}):
    with self.assertRaises(urllib.error.HTTPError):self.post(data)
   with self.assertRaises(urllib.error.HTTPError) as e:self.post({'text':'你好'},'https://example.org')
   self.assertEqual(e.exception.code,403)

if __name__=='__main__':unittest.main()
