"""Encode a timed 10-second review with music; fully decode both streams."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--wait-for-render',action='store_true');a=p.parse_args();out=Path(a.out)
if a.wait_for_render:
 deadline=time.monotonic()+1800
 while not (out/'render_report.json').exists() and not all((out/name).exists() for name in ['render_chunk_1_120.json','render_chunk_121_240.json']):
  assert time.monotonic()<deadline,'Timed out waiting for render ranges'
  for name in ['render_A.log','render_B.log']:
   if (out/name).exists():assert 'Traceback (most recent call last)' not in (out/name).read_text('utf8',errors='replace'),name
  time.sleep(3)
plan=json.loads((out/'render_plan.json').read_text('utf8'));assert plan['output_frames']==240 and plan['output_fps']==24
if not (out/'render_report.json').exists():
 chunks=[json.loads(q.read_text('utf8')) for q in sorted(out.glob('render_chunk_*.json'))]
 assert len(chunks)==2 and all(q['status']=='OUTPUT_FRAME_RANGE_COMPLETE' for q in chunks)
 rows=sorted([row for q in chunks for row in q['frames']],key=lambda q:q['output_frame'])
 assert [q['output_frame'] for q in rows]==list(range(1,241))
 render=dict(status='ALL_240_OUTPUT_FRAMES_COMPLETE',source_blend=chunks[0]['source_blend'],resolution=[1920,1080],fps=24,samples=24,parallel_workers=2,elapsed_s=max(q['end_epoch'] for q in chunks)-min(q['start_epoch'] for q in chunks),frames=rows)
 (out/'render_report.json').write_text(json.dumps(render,ensure_ascii=False,indent=2),'utf8')
render=json.loads((out/'render_report.json').read_text('utf8'));assert render['status']=='ALL_240_OUTPUT_FRAMES_COMPLETE'
manifest=[]
for row in plan['frames']:
 path=out/'frames'/f'f{row["output_frame"]:04d}.png'
 with Image.open(path) as im:assert im.size==(1920,1080);im.verify()
 manifest.append(dict(**row,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
music=Path(r'E:\data\music\Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3');assert music.exists()
video=out/'完整角色_7.5-17.5秒_1080p24fps_24采样_Shikako_预览.mp4';assert not video.exists()
def run(args,log):
 with (out/log).open('w',encoding='utf8') as stream:subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
seek=7.5+2/30;started=time.monotonic()
run([ffmpeg,'-hide_banner','-y','-framerate','24','-start_number','1','-i',str(out/'frames/f%04d.png'),'-ss',str(seek),'-i',str(music),'-map','0:v:0','-map','1:a:0','-t','10','-frames:v','240','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','24','-c:a','aac','-b:a','192k','-af','asetpts=PTS-STARTPTS','-movflags','+faststart',str(video)],'encode.log')
probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',check=True,creationflags=subprocess.CREATE_NO_WINDOW)
info=json.loads(probe.stdout);v=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_read_frames']))==(1920,1080,'24/1',240)
assert abs(float(v['duration'])-10)<.001 and abs(float(audio['duration'])-10)<.05
run([ffmpeg,'-v','error','-xerror','-i',str(video),'-map','0:v:0','-map','0:a:0','-f','null','NUL'],'full_decode.log');assert not (out/'full_decode.log').read_text('utf8').strip()
for seconds in [0,3.5,5,9.5]:
 run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(video),'-ss',str(seconds),'-frames:v','1','-y',str(out/f'decoded_{seconds:.1f}s.png')],f'decode_still_{seconds:.1f}.log')
physics=json.loads(Path(plan['physics_result']).read_text('utf8'));window=[r for r in physics['samples'] if 226<=r['frame']<=526]
report=dict(status='1080P_24FPS_240_FRAMES_10S_AUDIO_FULL_DECODE_PASS',video=str(video),bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),resolution=[1920,1080],fps=24,samples_per_pixel=24,video_frames=240,video_seconds=float(v['duration']),audio_seconds=float(audio['duration']),source_seconds=[7.5,17.5],source_fps=30,music=str(music),music_seek_seconds=seek,source_blend=render['source_blend'],physics_frames=physics['frames'],known_strain_warning_frames=len(physics['known_strain_warnings']),maximum_vertex_intrusion_depth_cm=max(r['maximum_depth_m'] for r in window)*100,zero_penetration_claim=False,physics_accepted=False,full_decode_pass=True,encode_and_verify_seconds=time.monotonic()-started,shutdown_forbidden=True)
(out/'ffprobe.json').write_text(probe.stdout,'utf8');(out/'frame_manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');(out/'video_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
