"""Encode and fully decode existing root-point review frames; no new render or dynamics."""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', required=True)
args = parser.parse_args()
root = Path(args.root)
render = json.loads((root / 'continuous_review/render_report.json').read_text(encoding='utf-8'))
bake = json.loads((root / 'bake_report.json').read_text(encoding='utf-8'))
assert bake['active_bones'] == 126 and not bake['strain_flags']
assert bake['no_collision_confirmed_in_every_observed_step']
assert render['new_simulation'] is False
fps, count = render['output_fps'], len(render['frames'])
for i in range(1,count+1):
    with (root / f'continuous_review/frames/f{i:04d}.png').open('rb') as stream:
        header = stream.read(26)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24]) == (1920,1080)
    assert header[24] == 8 and header[25] == 2, 'Mixed render formats'
caches = []
for path in sorted((root / 'cache').glob('*.pc2')):
    with path.open('rb') as stream:
        magic, version, points, start, step, samples = struct.unpack('<12siiffi',stream.read(32))
    assert magic == b'POINTCACHE2\x00' and version == 1
    assert path.stat().st_size == 32+points*samples*12
    caches.append(dict(path=str(path),points=points,samples=samples))
target = root / '完整头发_根部点锚定_无碰撞_3秒_1080p24fps.mp4'
zoom = root / '完整头发_根部点锚定_头发放大_3秒_1080p24fps.mp4'


def run(command):
    result = subprocess.run(command,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr[-4000:]
    return result


if not target.exists():
    run(['ffmpeg','-hide_banner','-loglevel','error','-n','-framerate',str(fps),'-start_number','1',
         '-i',str(root / 'continuous_review/frames/f%04d.png'),'-frames:v',str(count),'-c:v','libx264',
         '-preset','medium','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(target)])
if not zoom.exists():
    run(['ffmpeg','-hide_banner','-loglevel','error','-n','-i',str(target),'-vf',
         'crop=960:540:480:100,scale=1920:1080:flags=lanczos','-an','-c:v','libx264','-preset','medium',
         '-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(zoom)])
videos = []
for path in [target,zoom]:
    probe = json.loads(run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries',
               'stream=codec_name,width,height,avg_frame_rate,nb_read_frames:format=duration,size','-of','json',str(path)]).stdout)
    stream = probe['streams'][0]
    assert stream['width']==1920 and stream['height']==1080
    assert int(stream['nb_read_frames'])==count and stream['avg_frame_rate']==f'{fps}/1'
    assert abs(float(probe['format']['duration'])-count/fps)<.01
    run(['ffmpeg','-hide_banner','-loglevel','error','-xerror','-err_detect','explode','-i',str(path),'-map','0:v:0','-f','null','NUL'])
    videos.append(dict(path=str(path),metadata=probe,full_decode_passed=True,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
report = dict(status='ENCODED_AND_FULL_DECODE_PASSED',videos=videos,source_frames=count,
              main_video_full_character=True,zoom_is_crop_of_main_video=True,cache_headers_valid=caches,
              audio=False,new_simulation=False,new_render=False)
(root / 'video_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=report['status'],videos=[v['path'] for v in videos],frames=count,fps=fps),ensure_ascii=False))
