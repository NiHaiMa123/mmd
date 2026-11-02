"""Publish only actually simulated frames of the scoped native hair workflow."""
import argparse
import hashlib
import html
import json
import math
import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
p.add_argument('--mapping-check', required=True)
a = p.parse_args()
run, mapping = Path(a.run), Path(a.mapping_check)
r = json.loads((run / 'result.json').read_text('utf-8-sig'))
audit = json.loads((mapping / 'mapping_preservation_audit.json').read_text('utf8'))
assert r['samples'] and [x['frame'] for x in r['samples']] == list(range(1, r['frames'][1]+1))
complete = r['stop'] is None and r['frames'][1] == 450
depth_only = r.get('contact_limit_mode') == 'depth'
assert max(x['body_error_m'] for x in r['samples']) < 5e-6
last = r['frames'][1]
font_path = r'C:\Windows\Fonts\msyh.ttc'
font = ImageFont.truetype(font_path, 23)
small = ImageFont.truetype(font_path, 19)
title = ImageFont.truetype(font_path, 28)
verification_path = run / 'threshold_patch_verification.json'
verified = json.loads(verification_path.read_text('utf8')) if verification_path.exists() else None
if r['stop'] and r['stop'].get('over_5cm'):
    assert verified and verified['frame'] == last
    assert verified['classification'] == 'CONFIRMED_CONNECTED_OVER_5CM_PATCH'
    raw = Image.open(run / 'keyframes' / f'f{last:04d}.png').convert('RGB')
    sheet = Image.new('RGB', (1920, 860), '#111c2b')
    sheet.paste(raw.resize((1280,720), Image.Resampling.LANCZOS), (0,65))
    draw = ImageDraw.Draw(sheet)
    draw.text((20,16), f'完整头发连续模拟 · 原片 {(last-1)/30:.2f} 秒 · 超限后停止', font=title, fill='white')
    points = verified['patch_pixels']
    left,right=min(q[0] for q in points),max(q[0] for q in points)
    top,bottom=min(q[1] for q in points),max(q[1] for q in points)
    cx,cy=(left+right)/2,(top+bottom)/2
    crop=(int(cx-160),int(cy-180),int(cx+160),int(cy+180))
    sheet.paste(raw.crop(crop).resize((640,720),Image.Resampling.LANCZOS),(1280,65))
    draw.rectangle((left*2/3-8,65+top*2/3-8,right*2/3+8,65+bottom*2/3+8),outline='#ffbb55',width=3)
    path=[(1280+(q[0]-crop[0])*2,65+(q[1]-crop[1])*2) for q in verified['inside_path_pixels']]
    if len(path)>1: draw.line(path, fill='#ffca76',width=3)
    draw.text((1300,740),'橙线：埋入发片路径投影，保持正常材质',font=small,fill='#ffd899')
    names=' / '.join(verified['chains'])
    draw.text((20,800),f'{names}：连续范围 {verified["maximum_embedded_span_cm"]:.2f} cm，最深 {verified["maximum_depth_cm"]:.2f} cm。',font=font,fill='white')
    sheet.save(run / '完整角色_本轮停止位置.jpg',quality=95)
assets=run/'review_images'
assets.mkdir(exist_ok=True)
cards=[]
frames=[]
for path in sorted((run/'keyframes').glob('f*.png')):
    frame=int(path.stem[1:])
    assert frame<=last
    with Image.open(path) as im:
        assert im.size==(1920,1080)
        im.verify()
    im=Image.open(path).convert('RGB')
    im.resize((960,540),Image.Resampling.LANCZOS).save(assets/(path.stem+'_full.jpg'),quality=93)
    im.crop((650,110,1170,510)).save(assets/(path.stem+'_head.jpg'),quality=95)
    row=r['samples'][frame-1]
    label=f'原片 {(frame-1)/30:.2f} 秒 · 第 {frame} 帧'
    cards.append(f'<article id="f{frame}"><h2>{label}</h2><p>全头最大连片范围 {row["maximum_connected_extent_m"]*100:.2f} cm；最深 {row["maximum_depth_m"]*100:.2f} cm</p><a href="keyframes/{path.name}"><img class="full" src="review_images/{path.stem}_full.jpg"><img class="head" src="review_images/{path.stem}_head.jpg"></a></article>')
    frames.append(frame)
near=[f for f in [301,316,331,346,361] if f in frames]
if near:
    sheet=Image.new('RGB',(960*len(near),580),'#111c2b')
    draw=ImageDraw.Draw(sheet)
    for i,f in enumerate(near):
        im=Image.open(assets/f'f{f:04d}_full.jpg')
        sheet.paste(im,(i*960,40))
        draw.text((i*960+14,6),f'原片 {(f-1)/30:.1f} 秒 · 完整头发',font=font,fill='white')
    sheet.save(run/'11秒附近_完整角色对照.jpg',quality=95)
caches=[]
for path in sorted((run/'cache').glob('*.pc2')):
    with path.open('rb') as f:
        magic,version,count,start,step,samples=struct.unpack('<12siiffi',f.read(32))
    assert magic==b'POINTCACHE2\0' and path.stat().st_size==32+count*samples*12
    if path.name.startswith('ClassicHair_'):assert samples==last and start==1 and step==1
    caches.append(dict(file=path.name,points=count,start=start,step=step,samples=samples,
                       sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len([q for q in caches if q['file'].startswith('ClassicHair_')])==27
scope=f'已连续模拟并检查1–{last}帧（原片0–{(last-1)/30:.2f}秒）。'
if complete:
    outcome=('450帧已按用户最深埋入距离5厘米的门槛检查通过，连片范围仅作参考；' if depth_only else '450帧已按用户5厘米门槛检查通过；')+'仍有门槛以内的接触，不代表零穿模。'
elif r['stop']:
    outcome='出现实际超限或明显拉伸后已停止，没有继续修改参数。'
else:
    outcome='尚未完成450帧。'
if 331 not in frames:
    outcome+='11秒尚未获得有效模拟画面。'
stop_html=''
native_audit_path=run/'fringe_and_tail_stop_audit.json'
native_audit=json.loads(native_audit_path.read_text('utf8')) if native_audit_path.exists() else None
native_note=''
if native_audit:
    checked=[q['frame'] for q in native_audit['frames']]
    fringe=[next(c for c in q['chains'] if c['chain']=='FrontHair5-1.L') for q in native_audit['frames']]
    native_note=f'<p>新连续模拟独立复核帧{checked}：原刘海埋入顶点总数{sum(c["actual_inside_vertices"] for c in fringe)}，埋入面中心总数{sum(c["actual_inside_face_centers"] for c in fringe)}。<a href="fringe_and_tail_stop_audit.json">局部映射独立复核数据</a>。右长尾10.67秒的历史轻微接触最深约0.60厘米，按最新标准保留，不因埋入片段的范围去修改。</p>'
if verified:
    stop_html=f'<p>停止点独立重开复核：{html.escape(" / ".join(verified["chains"]))}，连片范围{verified["maximum_embedded_span_cm"]:.2f}厘米，最深{verified["maximum_depth_cm"]:.2f}厘米；{verified["fully_inside_edges"]}/{verified["tested_edges"]}条相邻边经1毫米间隔采样均位于身体内部。</p><img src="完整角色_本轮停止位置.jpg">'
strain_path=run/'stopped_review.json'
strain=json.loads(strain_path.read_text('utf8')) if strain_path.exists() else None
if r['stop'] and r['stop'].get('stretched_chains') and strain:
    raw=Image.open(run/'keyframes'/f'f{last:04d}.png').convert('RGB')
    sheet=Image.new('RGB',(1920,860),'#111c2b');sheet.paste(raw.resize((1280,720),Image.Resampling.LANCZOS),(0,65));draw=ImageDraw.Draw(sheet)
    draw.text((20,16),f'完整头发 · 原片 {(last-1)/30:.2f} 秒 · 拉伸检查位置（并非穿模超限）',font=title,fill='white')
    points=strain['edge_pixels'];cx=sum(q[0] for q in points)/2;cy=sum(q[1] for q in points)/2
    crop=(int(cx-160),int(cy-180),int(cx+160),int(cy+180));sheet.paste(raw.crop(crop).resize((640,720),Image.Resampling.LANCZOS),(1280,65))
    projected=[(1280+(q[0]-crop[0])*2,65+(q[1]-crop[1])*2) for q in points]
    draw.line(projected,fill='#ffca76',width=4)
    for x,y in projected:draw.ellipse((x-4,y-4,x+4,y+4),fill='#ffca76')
    draw.rectangle((min(q[0] for q in points)*2/3-8,65+min(q[1] for q in points)*2/3-8,max(q[0] for q in points)*2/3+8,65+max(q[1] for q in points)*2/3+8),outline='#ffbb55',width=3)
    draw.text((1300,740),'橙线：被测网格边的投影，可能被身体遮挡',font=small,fill='#ffd899')
    draw.text((20,800),f'{strain["display_chain"]}：被测边 {strain["initial_edge_m"]*100:.2f} → {strain["stopped_edge_m"]*100:.2f} cm；增加 {strain["edge_extension_m"]*100:.2f} cm。',font=font,fill='white')
    sheet.save(run/'完整角色_拉伸检查位置.jpg',quality=95)
    stop_html=f'<p>本轮未因浅埋或片段范围停止。第{last}帧，{strain["display_chain"]}的实际显示网格边从{strain["initial_edge_m"]*100:.2f}厘米伸长到{strain["stopped_edge_m"]*100:.2f}厘米（{strain["edge_ratio"]:.2f}倍）；同束原生物理代理边长P99为{strain["proxy"]["edge_ratio_p01_p99"][1]:.2f}倍，最大为{strain["proxy"]["maximum_edge_ratio"]:.2f}倍。发根和身体保持。这是本轮实际变形停止点，尚未继续更改物理或映射。</p><img src="完整角色_拉伸检查位置.jpg">'
intrusion_path=run/'independent_intrusion/intrusion_measurement.json'
if intrusion_path.exists():
    intrusion=json.loads(intrusion_path.read_text('utf8'))
    measurements='；'.join(f'{q["original_seconds"]:.1f}秒：顶点最深{q["maximum_vertex_inward_depth_cm"]:.2f}厘米、面中心最深{q["maximum_face_centroid_inward_depth_cm"]:.2f}厘米' for q in intrusion['frames'])
    native_note+=f'<p>独立全头深度复核：{measurements}，均未超过5厘米。<a href="independent_intrusion/intrusion_measurement.json">深度测量报告</a>。</p>'
policy_text='仅当最深埋入距离超过5厘米才处理；埋入片段范围只作参考，不作为停机条件。' if depth_only else '单个连通埋入范围或深度任一超过5厘米才处理。'
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>局部刘海绑定修正后的全头物理复查</title>
<style>body{{background:#111c2b;color:#e8f1ff;font:17px/1.6 system-ui,"Microsoft YaHei";margin:auto;max-width:1500px;padding:24px}}a{{color:#b5d5ff}}img{{width:100%}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}article{{background:#1b293e;padding:12px}}h2{{font-size:20px}}.head{{display:none}}body.detail .head{{display:block}}body.detail .full{{display:none}}button{{padding:10px;margin-right:12px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style>
<h1>局部刘海映射修正后的完整头发复查</h1><p>{scope}{outcome}</p>
<p>仅左刘海使用Blender原生Surface Deform直接传递代理表面变形，停止这三根骨骼的Damped Track；其余141根跟踪约束保持。27束物理仍为原生经典Cloth，参数未改；没有逐帧摆骨、修改原权重或身体动作。<a href="https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/surface_deform.html">Blender官方表面绑定说明</a>。</p>
<p>先复用现有233帧检查映射，原来7.73秒的左刘海顶点与面中心埋入均消除；抽查帧其他发束和身体坐标差为0。随后从第1帧连续重新模拟，未将PC2显示缓存用作物理续算状态。</p>{native_note}{stop_html}
<p>接触门槛：{policy_text}检测覆盖27束实际发片整帧顶点；没有证明连续时间、全部面内部或头发互碰/自碰。材质、完整脸眼头饰和地库保持，固定1920×1080全身镜头。短侧发扫过嘴前的自然度仍需视觉确认。服装暂停，抱手动作未改，自动关机保持取消。</p>
<p><a href="{html.escape(Path(r['blend']).name)}">本轮工程</a> · <a href="review_manifest.json">缓存与真实验证范围</a></p><button onclick="document.body.classList.remove('detail')">完整角色</button><button onclick="document.body.classList.add('detail')">完整头发细节</button><div class="grid">{''.join(cards)}</div></html>'''
(run/'查看本轮全头复查.html').write_text(page,'utf8')
manifest=dict(status='FULL_450_WITHIN_USER_LIMIT' if complete else 'STOPPED_ACTUAL_FAILURE',
              blend=r['blend'],actual_simulated_frames=r['frames'],continuous_checked_frames=len(r['samples']),
              rendered_frames=frames,eleven_second_full_character_available=331 in frames,
              caches=caches,local_mapping_audit=str(mapping/'mapping_preservation_audit.json'),
              stop=r['stop'],contact_limit_mode=r.get('contact_limit_mode','extent_or_depth'),physics_is_native=True,original_weights_edited=False,
              body_and_hug_preserved=True,zero_penetration_claim=False,shutdown_forbidden=True)
(run/'review_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(review=str(run/'查看本轮全头复查.html'),frames=frames,
                      simulated_through=last,eleven_second_available=331 in frames),ensure_ascii=False))
