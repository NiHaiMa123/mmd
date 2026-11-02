"""Finish publication and normal keyframe rendering after the whole-head guard."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet';parser=argparse.ArgumentParser();parser.add_argument('--run',default=str(P/'guard_component15'));parser.add_argument('--out',default=str(P/'FINAL_BULLET15'));args=parser.parse_args();RUN=Path(args.run);OUT=Path(args.out);OUT.mkdir(exist_ok=True)
PY=ROOT/'tools/contact_stack/venv/Scripts/python.exe';BLENDER=Path(r'D:\software\blender\5.2.1\blender.exe')
def status(stage,**extra):
 tmp=OUT/'preparation_status.tmp.json';tmp.write_text(json.dumps(dict(stage=stage,**extra),ensure_ascii=False,indent=2),'utf8');tmp.replace(OUT/'preparation_status.json');print(stage,extra,flush=True)
def python(script,*args):subprocess.run([str(PY),str(ROOT/'scripts'/script),*map(str,args)],check=True,cwd=ROOT)
def blender(script,*args):subprocess.run([str(BLENDER),'-b','-t','8','--python',str(ROOT/'scripts'/script),'--',*map(str,args)],check=True,cwd=ROOT)
try:
 status('WAITING_FOR_COMPLETE_GEOMETRY_GUARD')
 while True:
  state=json.loads((RUN/'status.json').read_text('utf8'))
  assert state['stage']!='FAILED',state
  if state['stage']=='GEOMETRY_GUARD_COMPLETE_REQUIRES_NATIVE_AND_VISUAL_QA':break
  time.sleep(5)
 status('PUBLISHING_COMPLETE_CACHE')
 python('publish_headless_hair.py','--run',RUN,'--out',OUT)
 status('ASSEMBLING_CLEAN_NORMAL_SCENE')
 blender('assemble_full_hair_showcase.py','--out',OUT)
 blend=OUT/'完整角色_整头连续物理_15秒.blend'
 blender('restore_soft_hair_shadows.py','--blend',blend)
 blender('finalize_full_hair_blend.py','--delivery',OUT)
 status('RENDERING_FULL_CHARACTER_NATIVE_KEYFRAMES')
 blender('render_full_hair_showcase.py','--source',blend,'--out',OUT/'keyframes','--frames','1,211,256,300,321,326,331,336,450','--percentage','100','--samples','32','--device','GPU')
 status('KEYFRAMES_READY_REQUIRES_AGENT_VISUAL_REVIEW')
except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
