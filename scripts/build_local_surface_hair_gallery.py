"""Publish 2 fps native full-character stills with the user's contact rule."""
import argparse,json,html,hashlib,math
from pathlib import Path
from PIL import Image,ImageFont,ImageDraw
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--allow-stopped',action='store_true');a=p.parse_args();out=Path(a.run)
result=json.loads((out/'result.json').read_text('utf8'));setup=json.loads((out/'setup.json').read_text('utf8'))
last=result['frames'][1];full=last==450 and result['stop'] is None
assert (full and result['status']=='CLASSIC_LOCAL_FRINGE_SURFACE_450_FRAMES_WITHIN_USER_5CM_DEPTH_LIMIT') or (a.allow_stopped and result['stop'])
assert setup.get('contact_limit_mode')=='depth' and result.get('contact_limit_mode')=='depth' and len(result['samples'])==last
assert not any(r['over_5cm'] for r in result['samples'])
assert max(r['body_error_m'] for r in result['samples'])<5e-6
rows=[r for r in result['samples'] if r['frame']>=151]
summary=dict(user_limit_cm=5,contact_limit_mode='depth',extent_used_for_acceptance=False,measurement='Every integer frame; all 24207 actual display-hair vertices; maximum inward distance to the closed-body boundary; connected patch spatial span is reference only',maximum_depth_cm=max(r['maximum_depth_m'] for r in rows)*100,maximum_connected_patch_extent_cm=max(r['maximum_connected_extent_m'] for r in rows)*100,frames_over_limit=0,zero_penetration_claim=False,limitations='Vertex sampling, not full continuous-time or exact face-interior proof',keyframes=[dict(original_seconds=(r['frame']-1)/30,maximum_depth_cm=r['maximum_depth_m']*100,maximum_connected_patch_extent_cm=r['maximum_connected_extent_m']*100) for r in rows if r['frame'] in [226,331,346,376]])
frames=list(range(151,last+1,15))
if frames[-1]!=last:frames.append(last)
if full:assert len(frames)==21
assets=out/'gallery';assets.mkdir(exist_ok=True);font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',18)
records=[];cards=[];fulltiles=[];headtiles=[]
for f in frames:
 path=out/'frames'/f'f{f:04d}.png'
 with Image.open(path) as raw:assert raw.size==(1920,1080);raw.verify()
 im=Image.open(path).convert('RGB');im.resize((960,540),Image.Resampling.LANCZOS).save(assets/f'full_{f:04d}.jpg',quality=93)
 crop=im.crop((650,110,1170,510));crop.save(assets/f'head_{f:04d}.jpg',quality=95)
 label=f'原片 {(f-1)/30:.2f}s · 帧 {f}'+(' · '+('结束帧' if full else '停止帧') if f==last else '')
 ft=Image.new('RGB',(640,396),'#182131');ft.paste(im.resize((640,360),Image.Resampling.LANCZOS),(0,36));ImageDraw.Draw(ft).text((12,5),label,font=font,fill='white');fulltiles.append(ft)
 ht=Image.new('RGB',(520,436),'#182131');ht.paste(crop,(0,36));ImageDraw.Draw(ht).text((12,5),label,font=font,fill='white');headtiles.append(ht)
 cards.append(f'<article id="f{f}"><h2>{html.escape(label)}</h2><a href="frames/f{f:04d}.png" target="_blank"><img class="full" loading="lazy" src="gallery/full_{f:04d}.jpg"><img class="head" loading="lazy" src="gallery/head_{f:04d}.jpg"></a></article>')
 records.append(dict(frame=f,original_seconds=(f-1)/30,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
for name,tiles,w,h in [('完整画面图集',fulltiles,640,396),('头发细节图集',headtiles,520,436)]:
 sheet=Image.new('RGB',(w*4,h*math.ceil(len(tiles)/4)),'#101722')
 for i,tile in enumerate(tiles):sheet.paste(tile,((i%4)*w,(i//4)*h))
 sheet.save(out/(name+'.jpg'),quality=95)
keytext='；'.join(f"{r['original_seconds']:.1f}秒：最深 {r['maximum_depth_cm']:.2f} cm" for r in summary['keyframes'])
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整角色 · 5–15秒 · 5厘米规则</title><style>*{box-sizing:border-box}body{margin:0;background:#101722;color:#eef3ff;font:16px system-ui,"Microsoft YaHei",sans-serif}header{padding:22px;background:#1b273af2;position:sticky;top:0;z-index:1}h1{font-size:24px;margin:0 0 8px}p{line-height:1.55;margin:5px 0;color:#c3cfe2}button{margin:8px 8px 0 0;padding:9px 15px;background:#344763;border:1px solid #6f88aa;border-radius:6px;color:white;cursor:pointer}a{color:#b5d5ff}.grid{padding:20px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:#1a2638;overflow:hidden;border-radius:8px;scroll-margin-top:230px}h2{font-size:16px;margin:0;padding:12px}img{width:100%;display:block}.head{display:none}body.detail .head{display:block}body.detail .full{display:none}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><header><h1>完整角色 · 原片5–15秒 · 仅按深度验收</h1><p>每0.5秒一张，共20张，另补结束帧；点击图片可查看1920×1080原图。没有生成视频。经典Cloth代理在左刘海使用原生Surface Deform，其余26束保留141根发骨的原生跟踪；保留原始权重；未启用发束自碰和互碰。</p><p>按你的规则：仅当最深埋入距离超过5厘米才处理；埋入片段范围只作参考。5厘米以内保留记录并继续。本轮逐帧顶点检查的最深埋入距离没有超过5厘米，仍有局部接触，不代表零穿模。</p><p>KEYTEXT</p><button onclick="document.body.classList.remove('detail')">完整画面</button><button onclick="document.body.classList.add('detail')">头发细节</button> <a href="#f226">7.5秒</a> · <a href="#f376">12.5秒</a> · <a href="完整画面图集.jpg">完整拼图</a> · <a href="头发细节图集.jpg">细节拼图</a></header><main class="grid">CARDS</main></html>'''.replace('KEYTEXT',keytext).replace('CARDS',''.join(cards))
if not full:
 page=page.replace('完整角色 · 5–15秒 · 5厘米规则',f'完整角色 · 已模拟5–{(last-1)/30:.2f}秒 · 埋入深度').replace('完整角色 · 原片5–15秒 · 仅按深度验收',f'完整角色 · 已模拟原片5–{(last-1)/30:.2f}秒 · 仅按深度验收')
 page=page.replace('每0.5秒一张，共20张，另补结束帧',f'每0.5秒一张，另补停止帧，共{len(frames)}张。另一束头发在{(last-1)/30:.2f}秒出现实际拉伸后停止，完整5–15秒尚未完成')
 page=page.replace('<a href="#f376">12.5秒</a>','<a href="#f331">11秒</a>')
(out/'查看图集.html').write_text(page,'utf8');(out/'contact_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
report=dict(status='COMPLETE_5_TO_15S_2FPS_GALLERY_WITHIN_USER_5CM_DEPTH_LIMIT' if full else 'PARTIAL_2FPS_GALLERY_STOPPED_FOR_ACTUAL_STRETCH',gallery=str(out/'查看图集.html'),images=len(frames),regular_sampling_fps=2,extra_endpoint_frame=last,resolution=[1920,1080],source_blend=result['blend'],raw_native_physics_cache=str(out/'cache'),video_generated=False,contact=summary,actual_simulated_frames=[1,last],complete_15s=full,stop=result['stop'],all_hair_collision_solved=False,records=records,shutdown_forbidden=True)
(out/'gallery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False),flush=True)
