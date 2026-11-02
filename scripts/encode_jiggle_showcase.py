"""Encode actual new frames and verify the complete video/audio decode."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--music',required=True);p.add_argument('--filename',default='完整角色_JigglePhysics_1080p_15秒_Shikako.mp4');a=p.parse_args();out=Path(a.delivery)
manifest=[]
for f in range(1,451):
    path=out/'frames'/f'f{f:04d}.png'
    with Image.open(path) as im:
        assert im.size==(1920,1080);im.verify()
    manifest.append(dict(frame=f,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
assert Path(a.filename).name==a.filename and Path(a.filename).suffix=='.mp4'
video=out/a.filename
with (out/'encode.log').open('w',encoding='utf8') as log:
    subprocess.run([ffmpeg,'-hide_banner','-y','-framerate','30','-start_number','1','-i',str(out/'frames/f%04d.png'),'-ss','.0666666667','-i',a.music,'-map','0:v:0','-map','1:a:0','-t','15','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)],stdout=log,stderr=subprocess.STDOUT,check=True)
probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',check=True)
info=json.loads(probe.stdout);v=next(x for x in info['streams'] if x['codec_type']=='video');audio=next(x for x in info['streams'] if x['codec_type']=='audio')
assert (v['width'],v['height'],v['r_frame_rate'],int(v['nb_read_frames']))==(1920,1080,'30/1',450)
assert abs(float(v['duration'])-15)<.001 and abs(float(audio['duration'])-15)<.04
with (out/'full_decode.log').open('w',encoding='utf8') as log:
    subprocess.run([ffmpeg,'-v','error','-i',str(video),'-f','null','NUL'],stdout=log,stderr=subprocess.STDOUT,check=True)
assert not (out/'full_decode.log').read_text('utf8').strip()
report=dict(status='VIDEO_AND_AUDIO_COMPLETE_DECODE_PASS',video=str(video),width=1920,height=1080,fps=30,frames=450,video_seconds=float(v['duration']),audio_seconds=float(audio['duration']),music=a.music,audio_seek_seconds=.0666666667,bytes=video.stat().st_size,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),physics_acceptance='see separate surface audit and visual review; this file verifies encoding only')
(out/'video_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');(out/'ffprobe.json').write_text(probe.stdout,'utf8');(out/'frame_manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
