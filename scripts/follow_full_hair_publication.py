"""Publish only newly checkpointed physical samples; exit on completion/failure."""
import argparse,json,time,subprocess,sys,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args();run=Path(a.run);out=Path(a.out);lock=out/'publication_follower.lock.json'
if lock.exists():
 old=json.loads(lock.read_text('utf8'))
 try:os.kill(old['pid'],0)
 except OSError:lock.rename(out/f'publication_follower_stale_{int(time.time())}.json')
 else:raise RuntimeError('Publication follower already running')
with lock.open('x',encoding='utf8') as f:json.dump(dict(pid=os.getpid(),created=time.time()),f)
try:
 while True:
  state=json.loads((run/'status.json').read_text('utf8'));assert state['stage']!='FAILED',state;latest=json.loads((run/'latest_state.json').read_text('utf8'));published=json.loads((out/'cache_publication.json').read_text('utf8'))
  if latest['sample']>published['published_through_sample'] or (state['stage']=='COMPLETE' and published['status']!='COMPLETE_PHYSICAL_TRAJECTORY'):
   subprocess.run([sys.executable,str(Path(__file__).with_name('publish_full_hair_cache.py')),'--input',a.input,'--run',a.run,'--out',a.out],check=True)
  if state['stage']=='COMPLETE':break
  time.sleep(5)
finally:
 if lock.exists() and json.loads(lock.read_text('utf8'))['pid']==os.getpid():lock.unlink()
