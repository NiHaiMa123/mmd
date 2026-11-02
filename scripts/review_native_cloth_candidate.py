"""Review a completed stock Cloth cache, with full-character native renders."""
import argparse,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BLENDER=r'D:\software\blender\5.2.1\blender.exe'
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args();out=Path(a.candidate)
source=out/'完整角色_原生发片Cloth_15秒.blend'
def status(stage,**kw):
    (out/'review_status.json').write_text(json.dumps(dict(stage=stage,**kw),ensure_ascii=False,indent=2),'utf8');print(stage,kw,flush=True)
def command(script,*args):return [BLENDER,'-b','-t','4','--python',str(ROOT/'scripts'/script),'--',*map(str,args)]
start=time.monotonic();status('WAITING_FOR_EXISTING_NATIVE_BAKE')
while True:
    state=json.loads((out/'status.json').read_text('utf8'))
    assert state['stage']!='FAILED',state
    if state['stage']=='BAKED_REQUIRES_ACTUAL_SURFACE_AND_VISUAL_REVIEW':break
    assert time.monotonic()-start<900,'Existing native bake did not finish';time.sleep(2)
status('NATIVE_KEYFRAME_RENDER_AND_CONTACT_AUDIT')
with (out/'keyframe_render.log').open('w',encoding='utf8') as renderlog:
    render=subprocess.Popen(command('render_full_hair_showcase.py','--source',source,'--out',out/'keyframes','--frames','1,69,192,230,247,256,331,338,345,450','--samples','32','--percentage','100','--device','GPU'),stdout=renderlog,stderr=subprocess.STDOUT)
    with (out/'keyframe_audit.log').open('w',encoding='utf8') as auditlog:
        subprocess.run(command('audit_jiggle_hair_candidate.py','--source',source,'--out',out/'audit','--frames','1,69,175,192,198,207,211,230,232,235,242,247,256,280,310,321,331,336,338,345,359,450','--containment'),stdout=auditlog,stderr=subprocess.STDOUT,check=True)
    assert render.wait()==0,'Native keyframe render failed'
audit=json.loads((out/'audit/surface_audit.json').read_text('utf8'))
status('KEYFRAMES_READY_REQUIRES_ACTUAL_AGENT_REVIEW',samples=audit['samples'],samples_with_crossings=audit['samples_with_crossings'],max_crossings=audit['max_crossings'])
