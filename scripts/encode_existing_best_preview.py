"""Verify fresh full-resolution frames, encode review video and decode fully.

Review output is explicitly not a zero-collision acceptance certificate.
"""
import argparse,json,subprocess,hashlib,shutil
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--music',required=True)
a=p.parse_args();out=Path(a.delivery);setup=json.loads((out/'setup.json').read_text('utf8'))
assert setup['frames']==[1,450] and setup['status']=='COMPLETED_EXISTING_PHYSICS_PACKAGED_FOR_VISUAL_REVIEW'
manifest=[]
for frame in range(1,451):
    path=out/'frames'/f'f{frame:04d}.png';assert path.exists(),frame
    with Image.open(path) as im:assert im.size==(1920,1080);im.verify()
    manifest.append(dict(frame=frame,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
video=out/'完整角色_现有最佳流程_1080p_15秒_Shikako_预览.mp4'
assert not video.exists(),'Do not replace an existing preview'
with (out/'encode.log').open('w',encoding='utf8') as log:
    subprocess.run([ffmpeg,'-hide_banner','-y','-framerate','30','-start_number','1','-i',str(out/'frames/f%04d.png'),
        '-ss','0.0666666667','-i',a.music,'-map','0:v:0','-map','1:a:0','-t','15','-c:v','libx264','-preset','medium','-crf','18',
        '-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',creationflags=subprocess.CREATE_NO_WINDOW,check=True)
info=json.loads(probe.stdout);v=next(s for s in info['streams'] if s['codec_type']=='video');audio=next(s for s in info['streams'] if s['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']))==(1920,1080,'30/1',450)
assert abs(float(v['duration'])-15)<.001 and abs(float(audio['duration'])-15)<.04
with (out/'full_decode.log').open('w',encoding='utf8') as log:
    subprocess.run([ffmpeg,'-v','error','-xerror','-i',str(video),'-f','null','NUL'],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
assert not (out/'full_decode.log').read_text('utf8').strip()
report=dict(status='EXISTING_BEST_PREVIEW_1080P_30FPS_450_FRAMES_15S_AUDIO_FULL_DECODE_PASS',
    video=str(video),bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
    width=1920,height=1080,fps=30,video_frames=int(v['nb_read_frames']),video_seconds=float(v['duration']),
    audio_seconds=float(audio['duration']),video_codec=v['codec_name'],audio_codec=audio['codec_name'],
    music=a.music,audio_seek_seconds=.0666666667,original_fixed_camera=True,all_hair_preserved=True,
    fresh_render_pool=True,source_physics=setup['source_blend'],new_bone_prototype_has_physics=False,
    all_hair_collision_solved=False,known_source_skin_crossing_frames=setup['source_known_skin_crossing_frames'],
    shutdown_forbidden=True)
(out/'video_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
(out/'frame_manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');(out/'ffprobe.json').write_text(probe.stdout,'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
