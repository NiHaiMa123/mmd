"""Run independent mesh checks and native full-character keyframe renders."""
import argparse,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BLENDER=r'D:\software\blender\5.2.1\blender.exe'
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args();out=Path(a.candidate)
def status(stage,**kw):
    (out/'review_status.json').write_text(json.dumps(dict(stage=stage,**kw),ensure_ascii=False,indent=2),'utf8');print(stage,kw,flush=True)
def command(script,*args):return [BLENDER,'-b','-t','4','--python',str(ROOT/'scripts'/script),'--',*map(str,args)]
start=time.monotonic()
while not (out/'bake_report.json').exists():
    if (out/'status.json').exists():
        state=json.loads((out/'status.json').read_text('utf8'));assert state['stage']!='FAILED',state
    assert time.monotonic()-start<180,'Bake not ready';time.sleep(1)
report=json.loads((out/'bake_report.json').read_text('utf8'));source=report['blend']
status('RENDERING_KEYFRAMES_AND_AUDITING_450_FRAMES')
with (out/'keyframe_render.log').open('w',encoding='utf8') as log:
    render=subprocess.Popen(command('render_full_hair_showcase.py','--source',source,'--out',out/'keyframes','--frames','1,69,175,242,256,310,331,336,345,450','--samples','32','--percentage','100','--device','GPU'),stdout=log,stderr=subprocess.STDOUT)
    with (out/'full450_audit.log').open('w',encoding='utf8') as auditlog:
        subprocess.run(command('audit_jiggle_hair_candidate.py','--source',source,'--out',out/'audit450','--first','1','--last','450','--step','1','--containment'),stdout=auditlog,stderr=subprocess.STDOUT,check=True)
    assert render.wait()==0,'Keyframe render failed'
audit=json.loads((out/'audit450/surface_audit.json').read_text('utf8'))
status('KEYFRAMES_READY_REQUIRES_ACTUAL_AGENT_REVIEW',samples=audit['samples'],samples_with_crossings=audit['samples_with_crossings'],max_crossings=audit['max_crossings'],elapsed_s=time.monotonic()-start)
