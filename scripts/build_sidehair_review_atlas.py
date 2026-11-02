"""Build a 2 fps still gallery from native full-character rendered frames."""
import argparse,html,json,math,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args();out=Path(a.delivery)
frames=list(range(151,451,15))+[450];assert len(frames)==21
assets=out/'gallery';assets.mkdir(exist_ok=True)
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',22)
small=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',18)
audit=json.loads((out/'audit300/surface_audit.json').read_text('utf8'));assert len(audit['rows'])==300
failed=[r for r in audit['rows'] if r['crossings']>0]
audit_summary=dict(sampling='Original frames 151..450, step 1 frame, actual displayed hair vs skin triangle intersections; no containment or continuous-time guarantee',sampled_frames=300,intersection_frames=len(failed),maximum_triangle_pairs=max(r['crossings'] for r in audit['rows']),maximum_body_error_m=max(r['body_error_m'] for r in audit['rows']),original_intersection_frame_numbers=[r['frame'] for r in failed],all_hair_collision_solved=False)
(out/'audit_summary.json').write_text(json.dumps(audit_summary,ensure_ascii=False,indent=2),'utf8')
records=[];cards=[];fulltiles=[];headtiles=[]
for i,f in enumerate(frames):
 path=out/'frames'/f'f{f:04d}.png'
 with Image.open(path) as raw:
  assert raw.size==(1920,1080);im=raw.convert('RGB')
 thumb=im.resize((960,540),Image.Resampling.LANCZOS);thumb.save(assets/f'full_{f:04d}.jpg',quality=92)
 crop=im.crop((650,110,1170,510));crop.save(assets/f'head_{f:04d}.jpg',quality=95)
 sec=(f-1)/30;label=f'原片 {sec:.2f}s  ·  帧 {f}'
 if f==450:label+='  ·  结束帧'
 ft=Image.new('RGB',(640,396),'#171b24');ft.paste(im.resize((640,360),Image.Resampling.LANCZOS),(0,36));ImageDraw.Draw(ft).text((12,5),label,font=small,fill='white');fulltiles.append(ft)
 ht=Image.new('RGB',(520,436),'#171b24');ht.paste(crop,(0,36));ImageDraw.Draw(ht).text((12,5),label,font=small,fill='white');headtiles.append(ht)
 cards.append(f'<article><h2>{html.escape(label)}</h2><a href="frames/f{f:04d}.png" target="_blank"><img class="full" loading="lazy" src="gallery/full_{f:04d}.jpg"><img class="head" loading="lazy" src="gallery/head_{f:04d}.jpg"></a></article>')
 records.append(dict(original_frame=f,original_time_seconds=sec,path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
for name,tiles,w,h in [('完整画面图集',fulltiles,640,396),('头发细节图集',headtiles,520,436)]:
 sheet=Image.new('RGB',(w*4,h*math.ceil(len(tiles)/4)),(13,16,22))
 for i,tile in enumerate(tiles):sheet.paste(tile,((i%4)*w,(i//4)*h))
 sheet.save(out/(name+'.jpg'),quality=94)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整角色 · 5–15 秒侧发复查图集</title><style>*{box-sizing:border-box}body{margin:0;background:#10131a;color:#eef1f7;font:16px system-ui,"Microsoft YaHei",sans-serif}header{padding:24px;position:sticky;top:0;background:#151a24f2;z-index:1}h1{margin:0 0 8px;font-size:24px}p{margin:6px 0;color:#bfc9dc}button{padding:9px 16px;margin:8px 6px 0 0;border:1px solid #57647b;border-radius:7px;color:white;background:#27344b;cursor:pointer}.grid{padding:20px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:#1b2230;border-radius:8px;overflow:hidden}h2{font-size:16px;padding:10px 14px;margin:0}img{display:block;width:100%;height:auto}.head{display:none}body.detail .full{display:none}body.detail .head{display:block}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><header><h1>完整角色 · 原片 5–15 秒</h1><p>每 0.5 秒一张，共 20 张；另补结束帧。点击任意图片查看原始 1920×1080 PNG。</p><p>两条短侧发使用原版 Jiggle 物理，改接精确身体网格。其他头发与身体动作沿用上一版。此图集用于视觉复查，不代表全段零穿模。</p><button onclick="document.body.classList.remove('detail')">完整画面</button><button onclick="document.body.classList.add('detail')">头发细节</button><a style="color:#a9c6ff" href="完整画面图集.jpg">完整拼图</a> · <a style="color:#a9c6ff" href="头发细节图集.jpg">细节拼图</a></header><main class="grid">'''+''.join(cards)+'</main></html>'
page=page.replace('此图集用于视觉复查，不代表全段零穿模。','短侧发悬浮已减轻；网格检查仍发现颈肩局部穿插，尚未完全修复。此图集用于视觉复查。')
(out/'查看图集.html').write_text(page,'utf8')
report=dict(status='NATIVE_RENDER_STILL_GALLERY_READY_WITH_KNOWN_RESIDUAL_CONTACT',source_frames=frames,regular_sampling_fps=2,regular_samples=20,extra_endpoint_frame=450,total_images=21,resolution=[1920,1080],video_generated=False,gallery=str(out/'查看图集.html'),full_contact_sheet=str(out/'完整画面图集.jpg'),hair_contact_sheet=str(out/'头发细节图集.jpg'),geometry_audit=audit_summary,records=records)
(out/'gallery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False),flush=True)
