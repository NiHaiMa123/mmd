"""Publish the local three-bone mapping test without implying a full bake passed."""
import argparse
import hashlib
import html
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
a = p.parse_args()
run = Path(a.run)
r = json.loads((run / 'result.json').read_text('utf8'))
v = json.loads((run / 'threshold_patch_verification.json').read_text('utf8'))
assert v['classification'] == 'CONFIRMED_CONNECTED_OVER_5CM_PATCH'
assert len(r['modified_bones']) == 3 and r['other_hair_bindings_preserved']
frame = v['frame']
source = Path(r['source_run'])
font_path = r'C:\Windows\Fonts\msyh.ttc'
font = ImageFont.truetype(font_path, 23)
small = ImageFont.truetype(font_path, 20)
title = ImageFont.truetype(font_path, 30)
raw = Image.open(run / 'keyframes' / f'f{frame:04d}.png').convert('RGB')
assert raw.size == (1920, 1080)
sheet = Image.new('RGB', (1920, 860), '#111c2b')
sheet.paste(raw.resize((1280, 720), Image.Resampling.LANCZOS), (0, 65))
draw = ImageDraw.Draw(sheet)
draw.text((22, 15), f'仅左侧刘海三骨验证 · 原片 {v["original_seconds"]:.2f} 秒 · 超限后停止', font=title, fill='white')
points = v['patch_pixels']
left, right = min(q[0] for q in points), max(q[0] for q in points)
top, bottom = min(q[1] for q in points), max(q[1] for q in points)
cx, cy = (left + right) / 2, (top + bottom) / 2
crop = (int(cx - 160), int(cy - 180), int(cx + 160), int(cy + 180))
sheet.paste(raw.crop(crop).resize((640, 720), Image.Resampling.LANCZOS), (1280, 65))
draw.rectangle((left * 2 / 3 - 8, 65 + top * 2 / 3 - 8,
                right * 2 / 3 + 8, 65 + bottom * 2 / 3 + 8), outline='#ffbb55', width=3)
projected = [(1280 + (q[0] - crop[0]) * 2, 65 + (q[1] - crop[1]) * 2)
             for q in v['inside_path_pixels']]
draw.line(projected, fill='#ffc56a', width=3)
for x, y in projected:
    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill='#ffc56a')
draw.text((1300, 740), '橙色：埋入发片路径的投影；并非外露轮廓', font=small, fill='#ffda99')
draw.text((22, 800), f'左刘海：连续埋入范围 {v["maximum_embedded_span_cm"]:.2f} cm，最深 {v["maximum_depth_cm"]:.2f} cm；'
          f'{v["fully_inside_edges"]}/{v["tested_edges"]} 条相邻边经 1 mm 间距采样复核。', font=font, fill='white')
image_name = '完整角色_局部刘海_停止位置.jpg'
sheet.save(run / image_name, quality=95)
caches = []
for path in sorted((run / 'cache').glob('*.pc2')):
    with path.open('rb') as f:
        magic, version, count, start, step, samples = struct.unpack('<12siiffi', f.read(32))
    assert magic == b'POINTCACHE2\0' and path.stat().st_size == 32 + count * samples * 12
    original = source / 'cache' / path.name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert original.exists() and digest == hashlib.sha256(original.read_bytes()).hexdigest()
    caches.append(dict(file=path.name, points=count, start=start, step=step,
                       samples=samples, sha256=digest, identical_to_source=True))
tested = [q['frame'] for q in r['keyframe_samples']]
manifest = dict(status='REJECTED_LOCAL_FRINGE_TARGET_Z_MAPPING', blend=r['blend'],
                modified_bones=r['modified_bones'], remaining_bindings_preserved=141,
                source=r['source'], available_cache_range=r['frames'],
                actually_tested_keyframes=tested,
                continuous_cached_frames_tested=[q['frame'] for q in r['samples']],
                stop_frame=frame, stop_seconds=v['original_seconds'],
                confirmed_chain=v['chains'], span_cm=v['maximum_embedded_span_cm'],
                depth_cm=v['maximum_depth_cm'], cache_files=caches,
                accepted=False, new_physics_started=False, body_motion_edited=False,
                original_weights_edited=False, shutdown_forbidden=True)
(run / 'review_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf8')
parts = ''.join(f'<a href="keyframes/f{f:04d}.png"><img src="keyframes/f{f:04d}.png"><span>原片 {(f-1)/30:.2f} 秒 · 第 {f} 帧</span></a>'
                for f in tested if (run / 'keyframes' / f'f{f:04d}.png').exists())
page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>局部刘海三骨映射复查</title><style>body{{max-width:1450px;margin:auto;padding:24px;background:#111c2b;color:#e8f1ff;font:17px/1.65 system-ui,"Microsoft YaHei"}}a{{color:#a8d2ff}}img{{width:100%}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style>
<h1>局部方向与扭转修正仍未通过，已停止</h1>
<p>本轮只把 FrontHair5-1.L、FrontHair5-2.L、FrontHair5-3.L 改为 Blender 原生 Track To（Target Z），其余141根保留原 Damped Track。复用相同的27束经典Cloth物理缓存，没有重新模拟，也没有改身体动作、原始权重和材质。</p>
<p>实际抽查关键帧 {html.escape(str(tested))}。第 {frame} 帧（原片 {v['original_seconds']:.2f} 秒），左刘海连续埋入范围 {v['maximum_embedded_span_cm']:.2f} 厘米，最深 {v['maximum_depth_cm']:.2f} 厘米，仍超过“范围或深度任一超过5厘米”的标准。上一版同处范围6.02厘米；本轮改善约0.67毫米，不能算解决。</p>
<img src="{image_name}"><p>独立重新打开保存的工程后，按1毫米间距检查连通网格边，{v['fully_inside_edges']}/{v['tested_edges']}条边的所有采样点均在皮肤内部，最远点之间存在全部位于内部的连接路径。橙线标记的是埋入发片的投影，所以正常材质画面里可能看不清；不是深埋5.95厘米，实际最深只有0.94厘米。</p>
<p>现有证据指向代理到原发骨及蒙皮的传递误差：上一版该处物理代理未进入身体，而显示发片进入身体。仅增加局部扭转方向约束未能消除误差，因此不能再把问题直接当作Cloth参数不足。本轮不继续盲调参数或启动全段渲染。</p>
<p>可用缓存含1–233帧，但本轮新映射只检查上述关键帧；没有完成逐帧检查，也没有验证11秒和12.5秒。完整5–15秒、每秒两帧图集仍未完成。另有短侧发扫过嘴前的自然度问题尚未解决。自动关机保持取消。</p>
<p><a href="{html.escape(Path(r['blend']).name)}">本轮未通过候选工程</a> · <a href="threshold_patch_verification.json">独立连片复核</a> · <a href="review_manifest.json">30份缓存逐文件一致性及真实验证范围</a></p><div class="grid">{parts}</div></html>'''
(run / '查看局部刘海复查.html').write_text(page, 'utf8')
print(json.dumps(dict(review=str(run / '查看局部刘海复查.html'), tested=tested,
                      unchanged_cache_files=len(caches), accepted=False), ensure_ascii=False))
