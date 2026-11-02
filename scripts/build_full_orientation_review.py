"""Publish actual checked frames and confirmed contact for a mapping test."""
import argparse,hashlib,html,json,struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));v=json.loads((run/'threshold_patch_verification.json').read_text('utf8'));assert v['classification']=='CONFIRMED_CONNECTED_OVER_5CM_PATCH';frame=v['frame'];source=Path(r['source_run'])
fontpath=r'C:\Windows\Fonts\msyh.ttc';font=ImageFont.truetype(fontpath,23);small=ImageFont.truetype(fontpath,20);title=ImageFont.truetype(fontpath,30)
raw=Image.open(run/'keyframes'/f'f{frame:04d}.png').convert('RGB');assert raw.size==(1920,1080)
sheet=Image.new('RGB',(1920,860),'#111c2b');sheet.paste(raw.resize((1280,720),Image.Resampling.LANCZOS),(0,65));draw=ImageDraw.Draw(sheet);draw.text((22,15),'完整旋转映射验证 · 第7帧（0.20秒）超限后停止',font=title,fill='white')
points=v['patch_pixels'];left=min(p[0] for p in points);right=max(p[0] for p in points);top=min(p[1] for p in points);bottom=max(p[1] for p in points);centre=((left+right)/2,(top+bottom)/2)
crop=(int(centre[0]-160),int(centre[1]-180),int(centre[0]+160),int(centre[1]+180));sheet.paste(raw.crop(crop).resize((640,720),Image.Resampling.LANCZOS),(1280,65))
draw.rectangle((left*2/3-8,65+top*2/3-8,right*2/3+8,65+bottom*2/3+8),outline='#ffbb55',width=3)
projected=[(1280+(p[0]-crop[0])*2,65+(p[1]-crop[1])*2) for p in v['inside_path_pixels']]
draw.line(projected,fill='#ffc56a',width=3)
for x,y in projected:draw.ellipse((x-3,y-3,x+3,y+3),fill='#ffc56a')
draw.text((1300,740),'橙色为埋入发片的投影，保持原正常材质',font=small,fill='#ffda99')
draw.text((22,800),f"辫发 Amikomi1：连片范围 {v['maximum_embedded_span_cm']:.2f} cm，最深 {v['maximum_depth_cm']:.2f} cm；{v['fully_inside_edges']}/{v['tested_edges']}条相邻边均在躯干内部。",font=font,fill='white')
sheet.save(run/'完整角色_完整旋转映射_停止位置.jpg',quality=95)
caches=[]
for path in sorted((run/'cache').glob('*.pc2')):
 with path.open('rb') as f:magic,version,count,start,step,samples=struct.unpack('<12siiffi',f.read(32))
 assert magic==b'POINTCACHE2\0' and path.stat().st_size==32+count*samples*12
 original=source/'cache'/path.name;assert original.exists();digest=hashlib.sha256(path.read_bytes()).hexdigest();assert digest==hashlib.sha256(original.read_bytes()).hexdigest()
 caches.append(dict(file=path.name,points=count,samples=samples,start=start,step=step,sha256=digest,identical_to_source=True))
tested=[q['frame'] for q in r['keyframe_samples']]
manifest=dict(status='REJECTED_FULL_ORIENTATION_MAPPING_ON_UNCHANGED_PHYSICS',blend=r['blend'],source=r['source'],source_run=r['source_run'],available_cached_range=r['frames'],actually_tested_keyframes=tested,continuous_cached_frames_tested=[q['frame'] for q in r['samples']],stop_frame=frame,stop_seconds=v['original_seconds'],confirmed_chain=v['chains'],span_cm=v['maximum_embedded_span_cm'],depth_cm=v['maximum_depth_cm'],cache_files=caches,new_physics_started=False,body_motion_edited=False,original_weights_edited=False,accepted=False,shutdown_forbidden=True)
(run/'review_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整旋转映射缓存复核</title><style>body{max-width:1450px;margin:auto;padding:24px;background:#111c2b;color:#e8f1ff;font:17px/1.65 system-ui,"Microsoft YaHei"}a{color:#a8d2ff}img{width:100%}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><h1>完整旋转复制候选未通过，已停止</h1><p>本轮在相同的27束Cloth缓存上，仅将144根发骨的Damped Track替换为原生Copy Rotation，并以初态校准旋转。身体、网格、权重、材质和所有物理缓存保持。没有重新运行物理，也没有调整物理参数。</p><p>实际只检查了关键帧1、7；第7帧（0.20秒）辫发Amikomi1出现连片埋入5.47厘米、最深2.58厘米。独立重开复核187/187条相邻边均在躯干内，确认超过用户5厘米规则。当前不采用这一全头复制旋转候选。</p><img src="完整角色_完整旋转映射_停止位置.jpg"><p>这只说明本候选的代理面到原骨架映射未通过；不能据此认定补扭转必然无效。新穿插位于此前未超限的辫子，后续若继续应保留有效发束的原有映射，将验证范围限于已确认出问题的刘海；不能把单个代理三角面的方向统一当作所有骨段应有的朝向。</p><p>上一版单轴发骨跟踪候选保留，其验证止于7.73秒。其余缓存虽然有1–233帧，本轮新映射没有查完该范围；11秒和12.5秒仍未验证，完整5–15秒图集未完成。自动关机保持取消。</p><p><a href="完整角色_Cloth发骨完整朝向_缓存复查.blend">本轮未通过候选</a> · <a href="threshold_patch_verification.json">独立连片复核</a> · <a href="review_manifest.json">缓存逐文件一致性及验证范围</a></p><div class="grid"><a href="keyframes/f0001.png"><img src="keyframes/f0001.png"></a><a href="keyframes/f0007.png"><img src="keyframes/f0007.png"></a></div></html>'''
(run/'查看完整旋转复查.html').write_text(page,'utf8');print(json.dumps(dict(review=str(run/'查看完整旋转复查.html'),tested=tested,unchanged_cache_files=len(caches),accepted=False),ensure_ascii=False))
