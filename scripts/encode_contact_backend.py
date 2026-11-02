"""Native 1080p numerical backend comparison with verified decode."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();folder=Path(a.input).resolve()
ffmpeg=Path('C:/Users/Administrator/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe');font=Path('C:/Windows/Fonts/arial.ttf');fontref=str(font).replace('\\','/').replace(':','\\:');frames=91
draw=lambda title:f"drawtext=fontfile='{fontref}':text='{title}':fontsize=30:fontcolor=white:x=24:y=28:box=1:boxcolor=black@0.65:boxborderw=10"
footer=f"drawtext=fontfile='{fontref}':text='0.90 s simulation - slowed playback - numerical probe only':fontsize=24:fontcolor=white:x=(w-tw)/2:y=h-48:box=1:boxcolor=black@0.65:boxborderw=9"
filters=f"[0:v]{draw('Unloaded joint')}[left];[1:v]{draw('Joint coupled to two cloth layers')}[right];[left][right]hstack=inputs=2,{footer}[v]"
out=folder/'Backend_JointCloth_1080p.mp4'
cmd=[str(ffmpeg),'-y','-framerate','30','-start_number','1','-i',str(folder/'preview_frames/free/%04d.png'),'-framerate','30','-start_number','1','-i',str(folder/'preview_frames/two_way/%04d.png'),'-filter_complex',filters,'-map','[v]','-frames:v',str(frames),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
result=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace')[-4000:])
info=json.loads(subprocess.check_output([str(ffmpeg.with_name('ffprobe.exe')),'-v','error','-show_streams','-show_format','-of','json',str(out)],text=True));stream=next(s for s in info['streams'] if s['codec_type']=='video');assert (stream['width'],stream['height'],int(stream['nb_frames']))==(1920,1080,frames)
subprocess.run([str(ffmpeg),'-v','error','-i',str(out),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
info.update(scope='Numerical single-hinge physical joint output and two cloth layers; not MMD acceptance',simulation_sample_time_span_s=.9,slow_playback=True,decode_verified=True)
(folder/'video_report.json').write_text(json.dumps(info,indent=2),encoding='utf-8');print(out)
