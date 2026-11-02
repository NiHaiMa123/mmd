"""Render disjoint GPU ranges, then verify/encode the existing-bake preview."""
import argparse,json,subprocess,time,sys,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--music',required=True)
p.add_argument('--workers',type=int,choices=[1,2],default=2)
a=p.parse_args();out=Path(a.delivery);repo=Path(__file__).resolve().parents[1]
setup=json.loads((out/'setup.json').read_text('utf8'));started=time.monotonic()
assert not (out/'video_report.json').exists(),'Verified preview already exists'
assert shutil.disk_usage(out).free>6*1024**3,'Need 6 GiB free for fresh 1080p frames'
def status(stage,**kw):
    r=dict(stage=stage,elapsed_s=time.monotonic()-started,available_frames=len(list((out/'frames').glob('f*.png'))),**kw)
    tmp=out/'delivery_status.tmp.json';tmp.write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'delivery_status.json')
    print(json.dumps(r,ensure_ascii=False),flush=True)
blender=r'D:\software\blender\5.2.1\blender.exe'
ranges=[(1,225),(226,450)] if a.workers==2 else [(1,450)]
jobs=[];logs=[]
for first,last in ranges:
    log=(out/f'render_{first:04d}.log').open('a',encoding='utf8');logs.append(log)
    argv=[blender,'--background','--factory-startup','--python',str(repo/'scripts/render_full_hair_showcase.py'),'--',
        '--source',setup['blend'],'--out',str(out/'frames'),'--first',str(first),'--last',str(last),
        '--samples','32','--percentage','100','--device','GPU']
    job=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,cwd=repo,creationflags=subprocess.CREATE_NO_WINDOW)
    jobs.append((job,first,last,argv))
(out/'render_jobs.json').write_text(json.dumps([dict(pid=j.pid,first=f,last=l,argv=argv) for j,f,l,argv in jobs],ensure_ascii=False,indent=2),'utf8')
try:
    while any(j.poll() is None for j,_,_,_ in jobs):
        status('RENDERING_FRESH_FULL_CHARACTER_FRAMES',workers=[dict(pid=j.pid,first=f,last=l,returncode=j.poll()) for j,f,l,_ in jobs])
        time.sleep(15)
    errors=[dict(pid=j.pid,first=f,last=l,returncode=j.returncode) for j,f,l,_ in jobs if j.returncode]
    if errors:raise RuntimeError(json.dumps(errors))
    status('VERIFYING_FRAMES_ENCODING_AND_FULL_DECODE')
    with (out/'encode_worker.log').open('a',encoding='utf8') as log:
        subprocess.run([sys.executable,'-X','utf8','-u',str(repo/'scripts/encode_existing_best_preview.py'),
            '--delivery',str(out),'--music',a.music],stdout=log,stderr=subprocess.STDOUT,cwd=repo,
            creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    report=json.loads((out/'video_report.json').read_text('utf8'));status('COMPLETE_PREVIEW_VIDEO_FULLY_DECODED',video=report['video'])
except BaseException as exc:
    status('FAILED_REPAIR_RENDER_OR_ENCODE',error=repr(exc));raise
finally:
    for log in logs:log.close()
