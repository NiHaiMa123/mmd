"""Verify and publish two short controls and a single-view comparison gallery."""
import argparse,hashlib,html,json,shutil,statistics,subprocess,time
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
review=json.loads((root/'review.json').read_text('utf8'));ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
reports=[]
for name in ['baseline01','soft_rear01']:
 run=root/name;render=run/'render';r=json.loads((render/'render_report.json').read_text('utf8'));assert r['status']=='CONTROL_72_FRAMES_COMPLETE' and len(r['frames'])==72
 frames=[]
 for i in range(1,73):
  image=render/'frames'/f'f{i:04d}.png'
  with Image.open(image) as im:assert im.size==(1920,1080);im.verify()
  frames.append(dict(frame=i,bytes=image.stat().st_size,sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
 video=run/('完整角色_'+('原参数' if name=='baseline01' else '柔顺候选')+'_转头急停_3秒1080p24fps.mp4')
 def call(args,log):
  with (render/log).open('w',encoding='utf8') as stream:subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
 if not video.exists():call([ffmpeg,'-hide_banner','-y','-framerate','24','-i',str(render/'frames/f%04d.png'),'-frames:v','72','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],'encode.log')
 probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(video)],capture_output=True,text=True,encoding='utf8',check=True,creationflags=subprocess.CREATE_NO_WINDOW);info=json.loads(probe.stdout);v=next(s for s in info['streams'] if s['codec_type']=='video');assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_read_frames']))==(1920,1080,'24/1',72) and abs(float(v['duration'])-3)<.001
 call([ffmpeg,'-v','error','-xerror','-i',str(video),'-f','null','NUL'],'full_decode.log');assert not (render/'full_decode.log').read_text('utf8').strip()
 report=dict(preset=r['preset'],video=str(video),relative_video=video.relative_to(root).as_posix(),resolution=[1920,1080],fps=24,samples=24,frames=72,duration_seconds=3,control_only=True,production_motion=False,full_decode_pass=True,sha256=hashlib.sha256(video.read_bytes()).hexdigest(),bytes=video.stat().st_size)
 reports.append(report);(render/'frame_manifest.json').write_text(json.dumps(frames,indent=2),'utf8');(render/'ffprobe.json').write_text(probe.stdout,'utf8')
(root/'video_reports.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),'utf8')
viewdata=[]
for name,r in zip(['baseline01','soft_rear01'],review['reviews']):
 stop=r['second_stop_display'];values=[stop['excursion_cm'][j] for j in review['rear_indices']]
 viewdata.append(dict(folder=name,title='原参数' if name=='baseline01' else '柔顺候选',video=reports[len(viewdata)]['relative_video'],stop_excursion_cm=round(statistics.median(values),2),depth_cm=round(r['maximum_depth_over_all_recorded_frames_cm'],2)))
data=json.dumps(viewdata,ensure_ascii=False).replace('</','<\\/')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整头发 · 转头急停对照</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101318;color:#eceef2;font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1440px;margin:auto;padding:24px}h1{font-size:27px;margin:0 0 8px}p{color:#b6bfcc}button,select{font:inherit;border:1px solid #4b5669;background:#222a35;color:white;border-radius:8px;padding:9px 16px;cursor:pointer}.active{background:#375b7b}nav{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.screen{aspect-ratio:16/9;overflow:hidden;background:#000;border-radius:12px}.screen video{width:100%;height:100%;display:block}.screen.close video{transform:scale(2.4);transform-origin:49% 19%}.info{background:#1b222d;border-radius:10px;padding:14px;margin-top:14px}.thumbs{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.thumbs img{width:100%;border-radius:8px;cursor:pointer}.thumbs p{margin:3px 0 12px;font-size:14px}a{color:#9acbff}details{margin:20px 0}table{border-collapse:collapse;width:100%;max-width:720px}td,th{padding:8px;border-bottom:1px solid #3a4352;text-align:left}</style>
<main><h1>完整头发 · 转头急停对照</h1><p>独立测试动作，非正片时间轴。全部 27 束头发、原银白材质、完整角色与地库背景均保留。0–0.5 秒转头，0.5–1 秒保持，1–1.5 秒回正，1.5–3 秒观察余动。</p>
<nav><button id="base">原参数</button><button id="soft" class="active">柔顺候选</button><button id="play">播放／暂停</button><button id="restart">从头播放</button><button id="zoom">放大完整头发</button></nav>
<div class="screen" id="screen"><video id="video" controls loop muted playsinline></video></div><div class="info" id="info"></div>
<p>切换参数时保留播放位置。放大按钮只改变网页显示范围，下载的视频仍为固定全身镜头。急停后的相对运动包含重力回落和碰撞响应，仍需观看连续画面判断是否自然。</p>
<h2>每半秒完整画面</h2><div class="thumbs" id="thumbs"></div>
<details><summary>本次改了什么</summary><p>只调整 18 束后发与长侧发；其余 9 束、原蒙皮、发根、碰撞体和质量保持一致。采用 Blender 原生 Cloth，没有逐帧修正发骨。左侧一束刘海沿用已绑定的原生 Surface Deform，其余沿用原生 Damped Track。</p><table><tr><th>参数</th><th>原参数</th><th>柔顺候选的 18 束</th></tr><tr><td>弯曲模型／刚度</td><td>Angular／25</td><td>Linear／0.5</td></tr><tr><td>空气阻尼</td><td>5</td><td>1</td></tr><tr><td>弹簧阻尼</td><td>25</td><td>5</td></tr><tr><td>顶点质量</td><td>0.005</td><td>0.005</td></tr><tr><td>拉伸／压缩／剪切刚度</td><td>1000</td><td>1000</td></tr><tr><td>场景重力</td><td>9.81</td><td>9.81</td></tr></table><p>参考 <a href="https://www.bilibili.com/video/BV1cD4y1R7U9?t=552">Sextet 的原生 Cloth 教程 09:12–09:18</a> 的弯曲和阻尼对比；本模型代理拓扑不同，未照抄教程全部数值。</p></details>
<p>3 秒，1920×1080，24fps，24 采样；两版均已完整解码验证。此短测试不能证明原舞蹈 11 秒或整段已经通过。原正片工程、抱手保护和原数据保留，服装仍暂停，关机未启用。</p><p><a href="review.json">网格与缓存复核</a> · <a href="video_reports.json">编码与完整解码记录</a></p></main>
<script>const data=__DATA__;let current=1;const v=document.getElementById('video'),info=document.getElementById('info'),thumbs=document.getElementById('thumbs');function set(i){const t=v.currentTime||0,paused=v.paused;current=i;v.src=data[i].video;v.onloadedmetadata=()=>{v.currentTime=Math.min(t,2.999);if(!paused)v.play()};document.getElementById('base').classList.toggle('active',i===0);document.getElementById('soft').classList.toggle('active',i===1);info.textContent=data[i].title+'｜回正后，18 束末端相对头部继续偏移的幅度中位数 '+data[i].stop_excursion_cm+' cm｜91 个整帧中最大顶点埋入 '+data[i].depth_cm+' cm（处理门槛 5 cm）';thumbs.innerHTML='';[1,16,31,46,61,76,91].forEach(f=>{const d=document.createElement('div'),im=document.createElement('img'),p=document.createElement('p');im.src=data[i].folder+'/keyframes/f'+String(f).padStart(4,'0')+'.png';im.alt='完整角色 '+((f-1)/30).toFixed(1)+' 秒';im.onclick=()=>{v.currentTime=Math.min((f-1)/30,2.999);v.pause()};p.textContent=((f-1)/30).toFixed(1)+' 秒';d.append(im,p);thumbs.append(d)})}document.getElementById('base').onclick=()=>set(0);document.getElementById('soft').onclick=()=>set(1);document.getElementById('play').onclick=()=>v.paused?v.play():v.pause();document.getElementById('restart').onclick=()=>{v.currentTime=0;v.play()};document.getElementById('zoom').onclick=()=>{document.getElementById('screen').classList.toggle('close')};set(1);</script></html>'''.replace('__DATA__',data)
(root/'完整头发_惯性与柔顺性对照.html').write_text(page,'utf8')
print(json.dumps(dict(status='CONTROL_GALLERY_AND_TWO_VIDEOS_FULL_DECODE_PASS',gallery=str(root/'完整头发_惯性与柔顺性对照.html'),videos=reports),ensure_ascii=False),flush=True)
