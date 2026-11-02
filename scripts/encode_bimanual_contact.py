"""Encode native 1080p two-panel contact comparison, verify full decode."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();folder=Path(a.input).resolve();qa=json.loads((folder/'blender_playback_qa.json').read_text(encoding='utf-8'))
if not qa['rendered_all']:raise RuntimeError('Full frame sequence required')
ffmpeg=Path('C:/Users/Administrator/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe');font='C\\:/Windows/Fonts/arial.ttf';frames=qa['frames']
def label(t):return f"drawtext=fontfile='{font}':text='{t}':fontsize=28:fontcolor=white:x=24:y=28:box=1:boxcolor=black@0.7:boxborderw=9"
filters=f"[0:v]{label('Same motors - no hand contact')}[a];[1:v]{label('Declared hand contact preserved')}[b];[a][b]hstack=inputs=2,drawtext=fontfile='{font}':text='1.5 s simulation - slowed playback - proxy joints only':fontsize=25:fontcolor=white:x=(w-tw)/2:y=h-50:box=1:boxcolor=black@0.7:boxborderw=9[v]"
out=folder/'Bimanual_Contact_1080p.mp4';cmd=[str(ffmpeg),'-y','-framerate','30','-start_number','1','-i',str(folder/'preview_frames/free/%04d.png'),'-framerate','30','-start_number','1','-i',str(folder/'preview_frames/contact/%04d.png'),'-filter_complex',filters,'-map','[v]','-frames:v',str(frames),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
r=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
info=json.loads(subprocess.check_output([str(ffmpeg.with_name('ffprobe.exe')),'-v','error','-show_streams','-show_format','-of','json',str(out)],text=True));stream=next(s for s in info['streams'] if s['codec_type']=='video')
if (stream['width'],stream['height'],int(stream['nb_frames']))!=(1920,1080,frames):raise RuntimeError('Video dimensions/count mismatch')
subprocess.run([str(ffmpeg),'-v','error','-i',str(out),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);info.update(decode_verified=True,scope=qa['scope'],simulation_seconds=qa['simulation_seconds'],slow_playback=True);(folder/'video_report.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(out)
