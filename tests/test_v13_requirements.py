import unittest,time,json
from pathlib import Path
import bag_engine as be
import product_questions as pq

class Offline(be.Engine):
 def interpret(self,text,c,history,targets,visible,deadline):return be.local_patch(text,c),'offline'
 def validated_wording(self,plan,context,deadline):return plan,False

class RequirementTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.goods=be.load_catalog(Path(__file__).resolve().parents[1]);cls.engine=Offline(cls.goods,None)
 def run_turn(self,text,c=None,**kw):return self.engine.handle(dict(text=text,conditions=c or {},**kw),time.monotonic()+20)
 def test_commute_does_not_imply_computer(self):
  r=self.run_turn('上班通勤');self.assertNotIn('needs_laptop',r['conditions']);self.assertNotIn('laptop',r['conditions'])
  self.assertNotIn('每天带电脑',r['reply']);self.assertTrue(all('电脑' not in t for t in r['product_texts'].values()))
 def test_cancellation_persists_and_can_be_reversed(self):
  for phrase in ['我上班不用带电脑','我不背电脑','电脑不用带','我不需要带笔记本了']:
   c={'scene':'通勤','needs_laptop':True,'laptop':16,'protection':'air','features':['电脑隔层','宽肩带'],'budget':300}
   r=self.run_turn(phrase,c);self.assertTrue(r['conditions']['without_laptop']);self.assertNotIn('laptop',r['conditions']);self.assertNotIn('needs_laptop',r['conditions']);self.assertNotIn('电脑隔层',r['conditions']['features']);self.assertEqual(r['conditions']['budget'],300)
   self.assertTrue(all('电脑' not in t for t in r['product_texts'].values()))
   nxt=self.run_turn('改成蓝色，其他不变',r['conditions']);self.assertTrue(nxt['conditions']['without_laptop']);self.assertNotIn('每天带电脑',nxt['reply'])
   yes=self.run_turn('现在需要带14寸电脑',nxt['conditions']);self.assertFalse(yes['conditions']['without_laptop']);self.assertEqual(yes['conditions']['laptop'],14)
 def test_model_cannot_infer_computer_from_scene_or_restore_it(self):
  def stale(*a,**kw):return json.dumps({'intent':'recommend','updates':{'scene':'通勤','needs_laptop':True,'laptop':16,'without_laptop':False,'features':['电脑隔层']},'remove':[]})
  engine=be.Engine(self.goods,stale)
  for c in [{},{'without_laptop':True,'budget':300}]:
   patch,_=engine.interpret('上班通勤',c,[],[],[],time.monotonic()+10);result=be.merge_state(c,patch);self.assertNotIn('needs_laptop',result);self.assertNotIn('laptop',result);self.assertNotIn('电脑隔层',result.get('features',[]))
 def test_hand_carry_direct_and_no_spec_dump(self):
  for id,lead in [(29,'【可以手提】'),(18,'【可以短距离手提】'),(3,'【没有独立手提把手】')]:
   r=self.run_turn('这款可以手提吗',target_ids=[id],action='analysis');text=r['product_texts'][str(id)];self.assertTrue(text.startswith(lead));self.assertNotRegex(text,'空包|英寸|好评')
 def test_hard_soft_separation(self):
  c=be.merge_state({},be.local_patch('想要夏天背舒服点，最好宽肩带，尽量简约，200元以内'))
  self.assertEqual(c['budget'],200);self.assertNotIn('maxweight',c);self.assertNotIn('features',c);self.assertIn('宽肩带',c['preferred_features']);self.assertIn('极简',c['preferred_aesthetics']);self.assertIn('透气',c['soft_preferences']);self.assertIn('背负舒适',c['soft_preferences'])
  strict=be.merge_state({},be.local_patch('必须宽肩带，至少20L'));self.assertIn('宽肩带',strict['features']);self.assertEqual(strict['capacity'],20)
 def test_capacity_conflict_and_choices(self):
  c={'budget':300};r=self.run_turn('容量至少30L，但不超过10L',c);self.assertEqual(r['conditions'],c);self.assertEqual(r['primary_ids'],[]);self.assertIn('无法同时满足',r['reply']);self.assertEqual(len(r['choices']),2)
  for choice in r['choices']:
   resolved=self.run_turn(choice,c);self.assertNotEqual(resolved['understanding_source'],'conflict-check')
 def test_priority_of_followups(self):
  self.assertEqual(be.followup({'water_need':'待确认'},[],[])[0],'scene')
  self.assertEqual(be.followup({'scene':'通勤','needs_laptop':True},[],[])[0],'laptop')
  self.assertEqual(be.followup({'scene':'通勤'},[],[])[0],'carrying')
  r=self.run_turn('带书本和水杯',{'scene':'通勤'});self.assertEqual(r['conditions']['scene'],'通勤')
 def test_capacity_upper_bound(self):
  r=self.run_turn('日常用，容量不超过15L');self.assertEqual(r['conditions']['capacity_max'],15)
  self.assertTrue(all(self.goods[i]['capacity']<=15 for i in r['primary_ids']+r['backup_ids']))
 def test_ordinal_reference_and_ambiguous_reference(self):
  r=self.run_turn('第二款防水吗',current_ids=[29,18,3]);self.assertEqual(r['ids'],[18]);self.assertIn('水',r['product_texts']['18'])
  r=self.run_turn('这款防水吗',current_ids=[29,18]);self.assertEqual(r['ids'],[]);self.assertIn('哪一款',r['reply'])
 def test_unknown_question_does_not_repeat_intro(self):
  r=self.run_turn('这款有保修吗',target_ids=[29],action='analysis');self.assertEqual(r['product_texts']['29'],'当前资料没有明确记录这一点，暂时不能直接确认。')

 def test_no_invented_numeric_constraints(self):
  def fabricate(*args,**kw):return json.dumps({'intent':'recommend','updates':{'scene':'通勤','maxweight':600,'capacity':25,'budget':500}})
  patch,_=be.Engine(self.goods,fabricate).interpret('上班用，轻一点',{},[],[],[],time.monotonic()+10)
  for field in ('maxweight','capacity','budget'):self.assertNotIn(field,patch['updates'])
 def test_preference_and_color_cancellation(self):
  c={'soft_preferences':['透气'],'preferred_features':['宽肩带'],'preferred_aesthetics':['极简'],'color':'蓝色'}
  r=self.run_turn('不需要透气了，不要求宽肩带，取消风格限制，不要蓝色了',c)
  self.assertNotIn('透气',r['conditions'].get('soft_preferences',[]));self.assertNotIn('宽肩带',r['conditions'].get('preferred_features',[]));self.assertNotIn('preferred_aesthetics',r['conditions']);self.assertNotIn('color',r['conditions']);self.assertIn('蓝色',r['conditions'].get('excluded_colors',[]))

 def test_common_carry_and_capacity_range(self):
  for phrase in ['要背电脑','带个电脑','需要携带笔记本']:
   c=be.merge_state({'without_laptop':True},be.local_patch(phrase));self.assertTrue(c['needs_laptop']);self.assertFalse(c['without_laptop'])
  r=self.run_turn('20到25L之间');self.assertEqual(r['conditions']['capacity'],20);self.assertEqual(r['conditions']['capacity_max'],25)
