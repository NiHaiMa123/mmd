"""Assemble the 7.5–15 second full-character review and strictly decode it."""
import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
p.add_argument('--wait-for-render', action='store_true')
a = p.parse_args()
out = Path(a.out)
reports = [out / 'render_chunk_1_90.json', out / 'render_chunk_91_180.json']
if a.wait_for_render:
    deadline = time.monotonic() + 1800
    while not all(q.exists() for q in reports):
        assert time.monotonic() < deadline, 'Render wait timed out'
        for letter in ['A', 'B']:
            path = out / f'render_{letter}.log'
            if path.exists():
                log = path.read_text('utf8', errors='replace')
                assert 'Traceback (most recent call last)' not in log, str(path)
                assert not ('Blender quit' in log and not reports[['A', 'B'].index(letter)].exists()), str(path)
        time.sleep(3)
plan = json.loads((out / 'render_plan.json').read_text('utf8'))
assert plan['output_frames'] == 180 and plan['output_fps'] == 24
assert plan['source_seconds'] == [7.5, 15]
collision_on = plan['collisions']
assert type(collision_on) is bool
chunks = [json.loads(q.read_text('utf8')) for q in reports]
assert all(q['status'] == 'OUTPUT_FRAME_RANGE_COMPLETE' for q in chunks)
assert all(q['source_blend'] == plan['source_blend'] for q in chunks)
rows = sorted([r for q in chunks for r in q['frames']], key=lambda r: r['output_frame'])
assert [r['output_frame'] for r in rows] == list(range(1, 181))
assert all(r['source_frame'] == 226 + (r['output_frame'] - 1) * 1.25 for r in rows)
assert all(r['camera_error'] == 0 for r in rows)
render = dict(status='ALL_180_OUTPUT_FRAMES_COMPLETE', source_blend=plan['source_blend'],
              resolution=[1920, 1080], fps=24, samples=24, parallel_workers=2,
              elapsed_s=max(q['end_epoch'] for q in chunks) - min(q['start_epoch'] for q in chunks),
              frames=rows)
(out / 'render_report.json').write_text(json.dumps(render, ensure_ascii=False, indent=2), 'utf8')
manifest = []
assert len(list((out / 'frames').glob('f*.png'))) == 180
for row in plan['frames']:
    path = out / 'frames' / f'f{row["output_frame"]:04d}.png'
    with Image.open(path) as im:
        assert im.size == (1920, 1080) and im.mode == 'RGB'
        im.verify()
    manifest.append(dict(**row, bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
assert ffmpeg and ffprobe
music = Path(r'E:\data\music\Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3')
assert music.exists()
mode = '原生碰撞' if collision_on else '无碰撞'
video = out / f'完整角色_7.5-15秒_根部点锚定_{mode}_1080p24fps_Shikako.mp4'
assert not video.exists()

def run(args, log):
    with (out / log).open('w', encoding='utf8') as stream:
        subprocess.run(args, stdout=stream, stderr=subprocess.STDOUT, check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)

def verify(path, prefix):
    probe = subprocess.run([ffprobe, '-v', 'error', '-count_frames', '-show_streams',
                            '-show_format', '-of', 'json', str(path)], capture_output=True,
                           text=True, encoding='utf8', check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    info = json.loads(probe.stdout)
    v = next(s for s in info['streams'] if s['codec_type'] == 'video')
    audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
    assert (v['width'], v['height'], v['avg_frame_rate'], int(v['nb_read_frames'])) == (1920, 1080, '24/1', 180)
    assert abs(float(v['duration']) - 7.5) < .001
    assert abs(float(audio['duration']) - 7.5) < .05
    run([ffmpeg, '-v', 'error', '-xerror', '-i', str(path), '-map', '0:v:0', '-map',
         '0:a:0', '-f', 'null', 'NUL'], prefix + '_full_decode.log')
    assert not (out / (prefix + '_full_decode.log')).read_text('utf8').strip()
    (out / (prefix + '_ffprobe.json')).write_text(probe.stdout, 'utf8')
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), frames=180,
                video_seconds=float(v['duration']), audio_seconds=float(audio['duration']),
                full_decode_pass=True)

seek = 7.5 + 2 / 30
started = time.monotonic()
run([ffmpeg, '-hide_banner', '-y', '-framerate', '24', '-start_number', '1', '-i',
     str(out / 'frames/f%04d.png'), '-ss', str(seek), '-i', str(music), '-map', '0:v:0',
     '-map', '1:a:0', '-t', '7.5', '-frames:v', '180', '-c:v', 'libx264', '-threads', '4',
     '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '24', '-c:a', 'aac',
     '-b:a', '192k', '-af', 'asetpts=PTS-STARTPTS', '-movflags', '+faststart', str(video)], 'encode.log')
main = verify(video, 'main')
for seconds in [0, 2, 3.5, 5, 7]:
    run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(video), '-ss', str(seconds),
         '-frames:v', '1', '-y', str(out / f'decoded_{seconds:.1f}s.png')], f'decode_still_{seconds:.1f}.log')
report = dict(status='1080P_24FPS_180_FRAMES_7_5S_AUDIO_FULL_DECODE_PASS',
              video=str(video), main=main, resolution=[1920, 1080], fps=24,
              samples_per_pixel=24, source_seconds=[7.5, 15], source_fps=30,
              music=str(music), music_seek_seconds=seek, source_blend=plan['source_blend'],
              bake_report=plan['bake_report'], collisions=collision_on, physics_accepted=False,
              full_decode_pass=True, render_seconds=render['elapsed_s'],
              encode_and_verify_seconds=time.monotonic() - started, shutdown_forbidden=True)
(out / 'frame_manifest.json').write_text(json.dumps(manifest, indent=2), 'utf8')
(out / 'video_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
print(json.dumps(report, ensure_ascii=False), flush=True)
