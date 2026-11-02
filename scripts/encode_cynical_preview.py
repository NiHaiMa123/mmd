"""Mux the 15-fps review render at real time with the supplied cover audio."""
import argparse,json,subprocess,struct
from pathlib import Path
FFMPEG=Path('C:/Users/Administrator/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe')
FFPROBE=FFMPEG.with_name('ffprobe.exe')
MUSIC=Path('E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3')


def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--audio-trim',type=float,default=2/30);a=p.parse_args();out=Path(a.fit).resolve()
    first=json.loads((out/'setup.json').read_text(encoding='utf-8'))['frames'][0]
    plan=json.loads((out/'render_plan.json').read_text(encoding='utf-8')) if (out/'render_plan.json').exists() else {'fps':15,'step':2}
    fps=plan['fps'];images=[out/'frames'/f'f{f:04d}.png' for f in range(first,first+450,plan['step'])]
    assert all(p.is_file() for p in images),'Missing preview frames'
    sizes=set()
    for path in images:
        with path.open('rb') as handle:
            header=handle.read(24);assert header[:8]==b'\x89PNG\r\n\x1a\n';sizes.add(struct.unpack('>II',header[16:24]))
    assert len(sizes)==1,'Mixed frame resolutions'
    if plan.get('native_render'):assert sizes=={(plan['width'],plan['height'])}
    concat=out/'preview.ffconcat';concat.write_text('ffconcat version 1.0\n'+''.join(f"file '{p.as_posix()}'\noption framerate {fps}\nduration {1/fps:.10f}\n" for p in images),encoding='utf-8')
    video_input=['-framerate',str(fps),'-start_number',str(first),'-i',str(out/'frames'/'f%04d.png')] if plan['step']==1 else ['-f','concat','-safe','0','-i',str(concat)]
    target=out/'Cynical_Cloth_15s_preview.mp4'
    cmd=[str(FFMPEG),'-hide_banner','-loglevel','error','-y',*video_input,'-ss',str(a.audio_trim),'-i',str(MUSIC),'-map','0:v:0','-map','1:a:0','-t','15','-r',str(fps),'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-af','asetpts=PTS-STARTPTS','-movflags','+faststart',str(target)]
    subprocess.run(cmd,check=True)
    info=json.loads(subprocess.check_output([str(FFPROBE),'-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,duration,nb_frames','-of','json',str(target)],text=True,encoding='utf-8'))
    assert abs(float(info['format']['duration'])-15)<.1
    assert any(s['codec_type']=='audio' for s in info['streams'])
    video=next(s for s in info['streams'] if s['codec_type']=='video');assert int(video['nb_frames'])==len(images)
    if plan.get('native_render'):assert (video['width'],video['height'])==(plan['width'],plan['height'])
    info.update({'output':str(target),'source_fps':30,'preview_fps':fps,'native_render':plan.get('native_render',False),'audio_trim_start_s':a.audio_trim,'scope':'first 15 seconds; native resolution from render_plan.json'})
    (out/'video_report.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CYNICAL_PREVIEW_ENCODED',json.dumps(info),flush=True)


if __name__=='__main__':main()
