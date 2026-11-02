"""Review an existing official-converter Cloth bake without restarting it."""
import argparse,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BLENDER=r'D:\software\blender\5.2.1\blender.exe'
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args();out=Path(a.candidate)
start=time.monotonic()
def status(stage,**kw):
 (out/'review_status.json').write_text(json.dumps(dict(stage=stage,**kw),ensure_ascii=False,indent=2),'utf8');print(stage,kw,flush=True)
def command(script,*args):return [BLENDER,'-b','-t','4','--python',str(ROOT/'scripts'/script),'--',*map(str,args)]
status('WAITING_FOR_EXISTING_NATIVE_BAKE')
while True:
 state=json.loads((out/'status.json').read_text('utf8'));assert state['stage']!='FAILED',state
 if state['stage']=='NATIVE_CLOTH_BAKED_REQUIRES_REVIEW':break
 assert time.monotonic()-start<900,'Existing bake did not finish';time.sleep(2)
source=state['blend'];status('FULL_CHARACTER_KEYFRAMES_AND_REAL_SURFACE_AUDIT')
with (out/'keyframe_render.log').open('w',encoding='utf8') as renderlog:
 job=subprocess.Popen(command('render_full_hair_showcase.py','--source',source,'--out',out/'keyframes','--frames','1,69,175,242,256,310,331,338,345,450','--samples','32','--percentage','100','--device','GPU'),stdout=renderlog,stderr=subprocess.STDOUT)
 with (out/'audit450.log').open('w',encoding='utf8') as auditlog:
  subprocess.run(command('audit_jiggle_hair_candidate.py','--source',source,'--out',out/'audit450','--first','1','--last','450','--step','1','--containment'),stdout=auditlog,stderr=subprocess.STDOUT,check=True)
 assert job.wait()==0
report=json.loads((out/'audit450/surface_audit.json').read_text('utf8'))
status('REQUIRES_ACTUAL_AGENT_REVIEW',samples=report['samples'],crossing_samples=report['samples_with_crossings'],max_crossings=report['max_crossings'])
