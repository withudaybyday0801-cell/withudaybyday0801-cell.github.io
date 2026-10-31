"""Local test fixture. Explicit parser + grounded catalog prose, NO model calls.
Never use this fixture as the production start command.
"""
import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bag_local as app
from bag_engine import Engine,local_patch
class OfflineEngine(Engine):
 def interpret(self,text,c,history,targets,visible,deadline):return local_patch(text,c),'offline-explicit-regression'
 def validated_wording(self,plan,context,deadline):return plan,False
app.KEY='offline-fixture-not-a-secret'
app.ENGINE=OfflineEngine(app.GOODS,None)
if __name__=='__main__':
 server=app.ThreadingHTTPServer(('127.0.0.1',int(os.getenv('BAG_TEST_PORT','8145'))),app.App)
 print('OFFLINE TEST FIXTURE: no AI service, no tokens',flush=True)
 server.serve_forever()
