import unittest,time
import bag_engine as be
import product_questions as pq
from pathlib import Path

class QuestionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.goods=be.load_catalog(Path(__file__).resolve().parents[1])
 def engine(self):
  def forbidden(*args,**kwargs):raise AssertionError('Known factual questions must not need a model')
  return be.Engine(self.goods,forbidden)
 def test_all_consumer_questions_all_products(self):
  for p in self.goods:
   for question in pq.COMMON_QUESTIONS:
    with self.subTest(sku=p['sku'],question=question):
     self.assertTrue(pq.asks_product_question(question));self.assertTrue(pq.topics(question))
     result=self.engine().handle(dict(text=question,target_ids=[p['id']],action='analysis',conditions={'color':'米色'},current_ids=[p['id']]),time.monotonic()+10)
     self.assertEqual(result['intent'],'analysis');self.assertEqual(result['ids'],[p['id']]);self.assertEqual(result['primary_ids'],[]);self.assertEqual(result['conditions'],{'color':'米色'})
     answer=result['product_texts'][str(p['id'])];self.assertTrue(answer);self.assertNotIn('为你挑选',answer);self.assertNotIn('需要留意：',answer)
 def test_analysis_all_named_products(self):
  class Offline(be.Engine):
   def validated_wording(self,plan,context,deadline):return plan,False
  for p in self.goods:
   result=Offline(self.goods,None).handle(dict(text='请分析商品「'+p['name']+'」。',target_ids=[p['id']],action='analysis',conditions={'scene':'校园'}),time.monotonic()+10)
   self.assertEqual(result['intent'],'analysis');self.assertEqual(result['ids'],[p['id']]);self.assertEqual(result['conditions'],{'scene':'校园'})
 def test_water_strap_answers_are_distinct(self):
  p=self.goods[29];water=pq.answer(p,'这款防水吗');strap=pq.answer(p,'这款肩带款吗')
  self.assertRegex(water,'雨|泼水');self.assertNotIn('空包',water);self.assertIn('cm',strap);self.assertNotEqual(water,strap)
 def test_mock_attributes_and_views(self):
  for p in self.goods:
   self.assertGreaterEqual(len(p['attributes']),19);self.assertEqual(set(p['image_views']),{'front','side','back'})
 def test_unknown_provided_data_not_assumed(self):
  answer=pq.answer({'name':'真实导入款'},'这款肩带宽吗，下雨会不会湿里面')
  self.assertIn('未提供',answer);self.assertNotIn('7.5',answer)
