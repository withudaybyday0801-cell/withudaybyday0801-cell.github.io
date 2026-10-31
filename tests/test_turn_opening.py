import json,time,unittest
from pathlib import Path
import bag_engine as be
from test_v13_requirements import Offline

class TurnOpeningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.goods=be.load_catalog(Path(__file__).resolve().parents[1]);cls.engine=Offline(cls.goods,None)
 def ask(self,text,c=None):return self.engine.handle({'text':text,'conditions':c or {}},time.monotonic()+20)
 def test_screenshot_sequence_and_first_sentence(self):
  c={'scene':'通勤'}
  prompts=[('上班用、不要太大','不想太大'),('至少 20L，最多 25L','20—25L'),('要装 14 寸电脑','14英寸')]
  replies=[]
  for text,expected in prompts:
   result=self.ask(text,c);c=result['conditions'];first=result['reply'].split('。')[0];self.assertIn(expected,first);self.assertNotIn('上班通勤，先看',first);replies.append(first)
   matches=be.search(self.goods,c);self.assertEqual(result['primary_ids'],[p['id'] for p in matches[:5]]);self.assertEqual(result['backup_ids'],[p['id'] for p in matches[5:10]])
   plan=be.recommendation_items(matches[:10],c);self.assertEqual(result['product_texts'],{str(i['id']):i['text'] for i in plan})
  self.assertEqual(len(set(replies)),3)
 def test_latest_request_beats_retained_context(self):
  c={'scene':'通勤','laptop':16,'needs_laptop':True,'capacity':20,'capacity_max':25,'budget':300,'color':'蓝色'}
  for text,expected in [('预算改成200元，其他不变','200元以内'),('改成黑色，其他不变','黑色'),('不带电脑了','不带电脑'),('容量最多25L','20—25L')]:
   r=self.ask(text,c);self.assertIn(expected,r['reply'].split('。')[0],text)
 def test_multiple_current_requirements(self):
  r=self.ask('20到25L，装14寸电脑，300元以内')
  self.assertTrue(r['primary_ids']);first=r['reply'].split('。')[0]
  for word in ('20—25L','14英寸','300元以内'):self.assertIn(word,first)
 def test_no_match_never_promises_match(self):
  r=self.ask('至少20L，最多25L，预算10元');self.assertEqual(r['primary_ids'],[]);self.assertIn('目前没有',r['reply']);self.assertNotIn('下面这几款符合',r['reply'])
 def test_soft_goal_does_not_claim_every_item_has_a_feature(self):
  for text,expected in [('上班用，希望耐脏好打理','耐脏'),('最好宽肩带','宽肩带')]:
   r=self.ask(text);self.assertIn(expected,r['reply'].split('。')[0]);self.assertNotIn('都有对应结构',r['reply'])
 def test_model_cannot_restore_the_generic_opening(self):
  p=self.goods[2];plan=be.blueprint('recommend',[p],[p],[],{'capacity':20,'capacity_max':25},'至少20L，最多25L')
  def writer(*args,**kw):return json.dumps({'opening':'上班通勤，先看包身轻便。','items':[{'id':2,'text':'空包510g，21L容量，日常收纳方便。'}],'closing':''})
  draft,_=be.Engine(self.goods,writer).validated_wording(plan,[p],time.monotonic()+20)
  self.assertEqual(draft['opening'],plan['opening']);self.assertIn('20—25L',draft['opening'])
