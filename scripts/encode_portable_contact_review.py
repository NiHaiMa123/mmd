import json,subprocess,struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';ffmpeg=Path('C:/Users/Administrator/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe');ffprobe=ffmpeg.with_name('ffprobe.exe');frames=out/'review_video_frames'
for mode in ('before','after'):
 for frame in range(1,451):
  p=frames/mode/f'f{frame:04}.png'
  with p.open('rb') as f:header=f.read(24)
  assert header[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',header[16:24])==(960,1080),p
overlay=Image.new('RGBA',(1920,80),(15,15,18,235));draw=ImageDraw.Draw(overlay);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',26);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',19)
draw.text((24,8),'SOURCE MOTION',font=font,fill='white');draw.text((984,8),'CONTACT CORRECTION / PARTIAL',font=font,fill='white');draw.text((24,46),'Upper-body diagnostic. Hip folds, hair and the transition into the protected clasp remain unresolved.',font=small,fill=(235,203,135,255));overlay.save(out/'review_caption.png')
target=out/'UpperBody_Contact_Comparison_1080p_15s.mp4';music=Path('E:/data/music/Shikako - シニカルナイトプラン（翻自 初音ミク）.mp3')
cmd=[str(ffmpeg),'-hide_banner','-loglevel','error','-y','-framerate','30','-start_number','1','-i',str(frames/'before/f%04d.png'),'-framerate','30','-start_number','1','-i',str(frames/'after/f%04d.png'),'-ss',str(2/30),'-i',str(music),'-i',str(out/'review_caption.png'),'-filter_complex','[0:v][1:v]hstack=inputs=2[views];[views][3:v]overlay=0:0:eof_action=repeat[v]','-map','[v]','-map','2:a:0','-frames:v','450','-t','15','-r','30','-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)]
subprocess.run(cmd,check=True)
info=json.loads(subprocess.check_output([str(ffprobe),'-v','error','-show_entries','format=duration:stream=codec_type,codec_name,width,height,duration,nb_frames','-of','json',str(target)],text=True,encoding='utf8'));v=next(s for s in info['streams'] if s['codec_type']=='video');assert int(v['nb_frames'])==450 and (v['width'],v['height'])==(1920,1080);assert abs(float(info['format']['duration'])-15)<.05
subprocess.run([str(ffmpeg),'-v','error','-i',str(target),'-f','null','-'],check=True)
info.update(output=str(target),scope='upper-body diagnostic only, partial correction, not full collision acceptance',decode_pass=True)
(out/'review_video_report.json').write_text(json.dumps(info,indent=2),encoding='utf8')
for f in (1,240,361):subprocess.run([str(ffmpeg),'-v','error','-y','-ss',str((f-1)/30),'-i',str(target),'-frames:v','1',str(out/f'comparison_f{f:04}.png')],check=True)
print('CONTACT_VIDEO_READY',str(target),flush=True)
