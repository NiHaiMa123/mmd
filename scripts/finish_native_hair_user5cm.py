"""Wait for the authorized physics job, then publish native stills only."""
import argparse,json,subprocess,time,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=Path(a.run);repo=Path(__file__).resolve().parents[1];started=time.monotonic()
blender=r'D:\software\blender\5.2.1\blender.exe'
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);tmp=out/'delivery_status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'delivery_status.json');print(json.dumps(row,ensure_ascii=False),flush=True)
def launch(script,args,logname):
 log=(out/logname).open('a',encoding='utf8');argv=[blender,'--background','--factory-startup','--python',str(repo/'scripts'/script),'--',*args]
 job=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,cwd=repo,creationflags=subprocess.CREATE_NO_WINDOW);return job,log
try:
 while not (out/'result.json').exists():
  current=json.loads((out/'status.json').read_text('utf8')) if (out/'status.json').exists() else {}
  assert current.get('stage')!='SCRIPT_INTERFACE_OR_SETUP_ERROR',current
  status('WAITING_FOR_USER_5CM_PHYSICS',physics=current);time.sleep(20)
 result=json.loads((out/'result.json').read_text('utf8'))
 if result['stop']:
  status('STOPPED_CONTACT_OVER_5CM_REQUIRES_REVIEW',physics=result['stop'],blend=result['blend']);sys.exit(0)
 assert result['frames']==[1,450] and result['status']=='NATIVE_SIDE_LOCKS_BAKED_WITHIN_USER_CONTACT_LIMIT'
 status('RENDERING_NATIVE_FULL_CHARACTER_2FPS_STILLS')
 frames=list(range(151,451,15))+[450]
 jobs=[launch('render_full_hair_showcase.py',['--source',result['blend'],'--out',str(out/'frames'),'--frames',','.join(map(str,frames)),'--device','GPU'],'render.log'),
       launch('measure_full_hair_intrusion.py',['--source',result['blend'],'--out',str(out/'key_surface_measurements'),'--frames','226,376,450'],'key_measure.log'),
       launch('audit_jiggle_hair_candidate.py',['--source',result['blend'],'--out',str(out/'audit300'),'--first','151','--last','450','--step','1'],'surface_audit.log')]
 while any(j.poll() is None for j,_ in jobs):
  status('RENDERING_NATIVE_FULL_CHARACTER_2FPS_STILLS',available_images=len(list((out/'frames').glob('f*.png'))));time.sleep(15)
 for j,log in jobs:log.close();assert j.returncode==0,(j.pid,j.returncode)
 status('PACKAGING_NATIVE_REVIEW_PROJECT_AND_VALIDATING_CACHES')
 j,log=launch('package_native_user5cm.py',['--run',str(out)],'package.log');assert j.wait()==0;log.close()
 with (out/'gallery_build.log').open('w',encoding='utf8') as stream:
  subprocess.run([sys.executable,'-X','utf8',str(repo/'scripts/build_native_hair_5cm_gallery.py'),'--run',str(out)],stdout=stream,stderr=subprocess.STDOUT,cwd=repo,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
 report=json.loads((out/'gallery_report.json').read_text('utf8'));status('COMPLETE_NATIVE_2FPS_GALLERY_WITH_USER_5CM_POLICY',gallery=report['gallery'])
except Exception as exc:status('FAILED_REPAIR_SCRIPT_OR_DELIVERY',error=repr(exc));raise
