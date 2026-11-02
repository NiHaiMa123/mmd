"""Render and fully decode the revised original 5..15 s review clip."""
import argparse,hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--music',required=True);a=p.parse_args()
out=Path(a.delivery);repo=Path(__file__).resolve().parents[1];started=time.monotonic()
setup=json.loads((out/'setup.json').read_text('utf8'));assert setup['frames']==[151,450]
assert not (out/'video_report.json').exists(),'Existing completed video must be preserved'
assert shutil.disk_usage(out).free>4*1024**3
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,available_frames=len(list((out/'frames').glob('f*.png'))),**kw)
 tmp=out/'delivery_status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'delivery_status.json');print(json.dumps(row,ensure_ascii=False),flush=True)
jobs=[];logs=[]
try:
 for first,last in [(151,300),(301,450)]:
  log=(out/f'render_{first}.log').open('a',encoding='utf8');logs.append(log)
  argv=[r'D:\software\blender\5.2.1\blender.exe','--background','--factory-startup','--python',str(repo/'scripts/render_full_hair_showcase.py'),'--','--source',setup['blend'],'--out',str(out/'frames'),'--first',str(first),'--last',str(last),'--samples','32','--percentage','100','--device','GPU']
  job=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,cwd=repo,creationflags=subprocess.CREATE_NO_WINDOW);jobs.append((job,first,last,argv))
 (out/'render_jobs.json').write_text(json.dumps([dict(pid=j.pid,first=f,last=l,argv=argv) for j,f,l,argv in jobs],ensure_ascii=False,indent=2),'utf8')
 while any(j.poll() is None for j,_,_,_ in jobs):
  status('RENDERING_REVISED_FULL_CHARACTER_5_TO_15_SECONDS',workers=[dict(pid=j.pid,first=f,last=l,returncode=j.poll()) for j,f,l,_ in jobs]);time.sleep(15)
 assert all(j.returncode==0 for j,_,_,_ in jobs),[(j.pid,j.returncode) for j,_,_,_ in jobs]
 status('CHECKING_300_FRESH_1080P_FRAMES')
 manifest=[]
 for f in range(151,451):
  path=out/'frames'/f'f{f:04d}.png'
  with Image.open(path) as im:assert im.size==(1920,1080);im.verify()
  manifest.append(dict(original_frame=f,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
 ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
 video=out/'完整角色_侧发阻尼修正_原片5至15秒_1080p_Shikako.mp4';assert not video.exists()
 def run(argv,log):
  with (out/log).open('w',encoding='utf8') as stream:subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
 status('ENCODING_WITH_SYNCHRONIZED_MUSIC')
 run([ffmpeg,'-hide_banner','-y','-framerate','30','-start_number','151','-i',str(out/'frames/f%04d.png'),'-ss',str(setup['audio_seek_seconds']),'-i',a.music,'-map','0:v:0','-map','1:a:0','-t','10','-frames:v','300','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)],'encode.log')
 probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW,check=True)
 info=json.loads(probe.stdout);v=next(s for s in info['streams'] if s['codec_type']=='video');au=next(s for s in info['streams'] if s['codec_type']=='audio')
 assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']))==(1920,1080,'30/1',300)
 assert abs(float(v['duration'])-10)<.001 and abs(float(au['duration'])-10)<.04
 status('FULL_VIDEO_AND_AUDIO_DECODE')
 run([ffmpeg,'-v','error','-xerror','-i',str(video),'-f','null','NUL'],'full_decode.log');assert not (out/'full_decode.log').read_text('utf8').strip()
 report=dict(status='REVISED_FULL_CHARACTER_1080P_30FPS_300_FRAMES_10S_AUDIO_FULL_DECODE_PASS',video=str(video),bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),width=1920,height=1080,fps=30,video_frames=300,video_seconds=float(v['duration']),audio_seconds=float(au['duration']),source_frames=[151,450],audio_seek_seconds=setup['audio_seek_seconds'],music=a.music,blend=setup['blend'],original_full_head_and_materials=True,original_fixed_camera=True,no_per_frame_manual_hair_correction=True,all_hair_collision_solved=False,shutdown_forbidden=True)
 (out/'video_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');(out/'frame_manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');(out/'ffprobe.json').write_text(probe.stdout,'utf8')
 status('COMPLETE_REVISED_10S_CLIP_FULL_DECODE_PASS',video=str(video))
except BaseException as exc:status('FAILED_RENDER_OR_ENCODE',error=repr(exc));raise
finally:
 for log in logs:log.close()
