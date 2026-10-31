"""Run the 25 original prompts against a deployed V10 service.

Uses the service's existing model configuration, never asks for or transmits a key.
This WILL consume model tokens on that service. Run only on your own deployment.
"""
import argparse,json,time,sys,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bag_engine import match

def request(url,data=None):
 raw=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
 with urllib.request.urlopen(urllib.request.Request(url,data=raw,headers={'Content-Type':'application/json'}),timeout=195) as r:return json.load(r)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('url');parser.add_argument('--output',default='live-acceptance-results.json');args=parser.parse_args()
 base=args.url.rstrip('/');init=request(base+'/api/init')
 if init.get('catalog_version')!='v10':raise SystemExit('请先部署V10，再执行验收；本脚本不会测试旧版本。')
 if not init.get('status',{}).get('chat'):raise SystemExit('网页未配置模型服务。请先在Render设置BAG_AI_KEY。')
 goods=init['goods'];cases=json.loads((ROOT/'tests/acceptance_cases.json').read_text());results=[];group=None;state={};asked=[];skip=[];history=[];visible=[]
 for case in cases:
  if case['group']!=group:state={};asked=[];skip=[];history=[];visible=[];group=case['group']
  body=dict(text=case['text'],conditions=state,asked=asked,skip=skip,history=history[-10:],current_ids=visible,action=case.get('action','auto'),target_ids=case.get('target_ids',[]))
  start=time.monotonic();problems=[]
  try:
   result=request(base+'/api/chat',body)
   if result.get('understanding_source','').startswith('offline'):problems.append('连接的是离线测试夹具，并非真实模型服务')
   for key,value in case['expected_conditions'].items():
    if result.get('conditions',{}).get(key)!=value:problems.append(f'条件错误：{key}')
   for key in case['absent_conditions']:
    if key in result.get('conditions',{}):problems.append(f'条件未删除：{key}')
   if case['expected_primary_count'] is not None and len(result.get('primary_ids',[]))!=case['expected_primary_count']:problems.append('推荐数量错误')
   for id in result.get('primary_ids',[])+result.get('backup_ids',[]):
    if not match(goods[id],result['conditions'])[0]:problems.append(f'商品不符合条件：{goods[id]["name"]}')
   if case['id']>=21 and result.get('question'):problems.append('分析/比较不应追问')
   if case['id']==21 and '510g' not in result.get('product_texts',{}).get('2',''):problems.append('重量不一致')
   if case['id']==25 and '214g' not in result.get('reply',''):problems.append('重量差计算不一致')
   state=result.get('conditions',state);asked=result.get('asked',asked);skip=result.get('skip',skip);visible=result.get('primary_ids') or result.get('ids',visible)
   history.extend([{'role':'user','content':case['text']},{'role':'assistant','content':result.get('reply','')}])
   entry=dict(id=case['id'],text=case['text'],status='failed' if problems else 'passed',problems=problems,result=result,seconds=round(time.monotonic()-start,2))
  except Exception as error:entry=dict(id=case['id'],text=case['text'],status='failed',problems=[str(error)],seconds=round(time.monotonic()-start,2))
  results.append(entry);Path(args.output).write_text(json.dumps({'scope':'real-deployed-service-and-model','results':results},ensure_ascii=False,indent=2),encoding='utf-8');print(case['id'],entry['status'],entry['problems'],flush=True)
 failed=sum(r['status']=='failed' for r in results);print(f'通过 {len(results)-failed}/{len(results)}；详细记录：{args.output}')
 raise SystemExit(1 if failed else 0)
if __name__=='__main__':main()
