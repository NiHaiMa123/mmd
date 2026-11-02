"""Render and verify the full new 15s video after agent keyframe review."""
import argparse,json,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];P=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet';parser=argparse.ArgumentParser();parser.add_argument('--delivery',default=str(P/'FINAL_SMOOTH15'));args=parser.parse_args();OUT=Path(args.delivery);PY=ROOT/'tools/contact_stack/venv/Scripts/python.exe';BLENDER=Path(r'D:\software\blender\5.2.1\blender.exe');jobs=[]
def status(stage,**extra):
 q=OUT/'delivery_status.tmp.json';q.write_text(json.dumps(dict(stage=stage,**extra),ensure_ascii=False,indent=2),'utf8');q.replace(OUT/'delivery_status.json');print(stage,extra,flush=True)
def py(script,*args):subprocess.run([str(PY),str(ROOT/'scripts'/script),*map(str,args)],check=True,cwd=ROOT)
def ba(script,*args):return [str(BLENDER),'-b','-t','8','--python',str(ROOT/'scripts'/script),'--',*map(str,args)]
def check_audits():
 for job,_,name in jobs:assert job.poll() in [None,0],('Independent native audit failed',name,job.returncode)
def render(frames):
 job=subprocess.Popen(ba('render_full_hair_showcase.py','--source',OUT/'完整角色_整头连续物理_15秒.blend','--out',OUT/'frames','--frames',','.join(map(str,frames)),'--percentage','100','--samples','32','--device','GPU'),cwd=ROOT)
 try:
  while job.poll() is None:check_audits();time.sleep(2)
  assert job.returncode==0,('Renderer failed',job.returncode)
 except BaseException:
  if job.poll() is None:
   job.terminate()
   try:job.wait(timeout=20)
   except subprocess.TimeoutExpired:job.kill();job.wait()
  raise
try:
 assert json.loads((OUT/'agent_visual_review.json').read_text('utf8'))['decision']=='PASS'
 status('RUNNING_INDEPENDENT_NATIVE_AUDITS_AND_RENDERING_CONTINUOUS_REVIEW')
 for name,first,last in [('native_part_a',1,225),('native_part_b',225.125,450)]:
  stream=(OUT/(name+'.log')).open('w',encoding='utf8');job=subprocess.Popen(ba('audit_full_hair_showcase.py','--delivery',OUT,'--first',first,'--last',last,'--step','.125','--name',name),stdout=stream,stderr=subprocess.STDOUT,cwd=ROOT);jobs.append((job,stream,name))
 (OUT/'native_audit_jobs.json').write_text(json.dumps([dict(pid=job.pid,name=name) for job,_,name in jobs],indent=2),'utf8')
 render(range(301,361))
 ffmpeg='ffmpeg'
 subprocess.run([ffmpeg,'-hide_banner','-y','-framerate','30','-start_number','301','-i',str(OUT/'frames/f%04d.png'),'-frames:v','60','-vf','scale=960:540','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(OUT/'11秒附近_连续复查.mp4')],check=True,cwd=ROOT)
 status('CONTINUOUS_REVIEW_READY_REQUIRES_AGENT_REVIEW',video=str(OUT/'11秒附近_连续复查.mp4'))
 while not (OUT/'agent_continuous_review.json').exists():check_audits();time.sleep(3)
 assert json.loads((OUT/'agent_continuous_review.json').read_text('utf8'))['decision']=='PASS'
 status('RENDERING_ALL_450_NATIVE_FRAMES')
 render(list(range(1,301))+list(range(361,451)))
 status('WAITING_FOR_NATIVE_AUDITS')
 for job,stream,name in jobs:
  code=job.wait();stream.close();assert code==0,(name,code)
 py('merge_full_hair_native_audits.py','--delivery',OUT,'--reports','native_part_a.json','native_part_b.json')
 subprocess.run(ba('audit_render_hair_raw_surfaces.py','--delivery',OUT,'--out',OUT/'raw_surface_audit','--frames','211,256,300,321,326,331,336,450'),check=True,cwd=ROOT)
 raw=json.loads((OUT/'raw_surface_audit/raw_surfaces.json').read_text('utf8'));assert all(r['crossings']==0 for r in raw['rows']),raw['rows']
 subprocess.run(ba('audit_full_hair_showcase.py','--delivery',OUT,'--frames','211,256,300,321,326,331,336,450','--full-containment','--name','full_containment_audit'),check=True,cwd=ROOT)
 subprocess.run(ba('verify_full_hair_source_preservation.py','--delivery',OUT,'--source',ROOT.parent/'work/headswap_xl_codex/hair_initial_repair_20261030/DELIVER_INITIAL/完整角色_第1帧全头初态_身体避碰通过.blend'),check=True,cwd=ROOT)
 py('audit_headless_hair_motion.py','--delivery',OUT)
 status('ENCODING_AND_FULL_DECODING')
 py('encode_full_hair_showcase.py','--delivery',OUT,'--music',r'E:\data\music\Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3','--filename','完整角色_MMD物理与发片避碰_1080p_15s_Shikako.mp4')
 py('build_headless_repro_bundle.py','--delivery',OUT)
 py('finalize_headless_delivery_report.py','--delivery',OUT)
 status('COMPLETE_VIDEO_BLEND_CACHES_AND_REPRO_BUNDLE_VERIFIED')
except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
