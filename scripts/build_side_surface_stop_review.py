"""Data-driven review figure and normal still links for a stopped native run."""
import argparse, hashlib, html, json, struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

p = argparse.ArgumentParser()
p.add_argument('--run', required=True)
a = p.parse_args()
run = Path(a.run)
r = json.loads((run / 'result.json').read_text('utf8'))
v = json.loads((run / 'threshold_patch_verification.json').read_text('utf8'))
setup = json.loads((run / 'setup.json').read_text('utf8'))
assert r['status'] == 'STOPPED_NATIVE_SURFACE_CONTACT_OR_STRETCH'
assert v['classification'] == 'CONFIRMED_CONNECTED_OVER_5CM_PATCH'
assert all(not q['over_5cm'] for q in v['side_surface_display_contacts'])
font_path = r'C:\Windows\Fonts\msyh.ttc'
font = ImageFont.truetype(font_path, 22)
small = ImageFont.truetype(font_path, 19)
title = ImageFont.truetype(font_path, 30)
sheet = Image.new('RGB', (1440, 760), '#111b29')
draw = ImageDraw.Draw(sheet)
draw.text((25, 15), '完整头发复查 · 原生薄面物理 · 已按5厘米规则停止', font=title, fill='white')
crop = (700, 120, 1150, 480)
for x, frame, label in [(25, 226, '7.50秒：逐顶点检查未检出埋入'), (740, v['frame'], '7.73秒：左侧刘海被左上臂遮住')]:
    source = run / 'keyframes' / f'f{frame:04d}.png'
    with Image.open(source) as im:
        assert im.size == (1920, 1080)
        sheet.paste(im.convert('RGB').crop(crop).resize((675, 540), Image.Resampling.LANCZOS), (x, 115))
    draw.text((x, 78), label, font=font, fill='white')
    if frame == v['frame']:
        def xy(pt):
            return (x + (pt[0] - crop[0])*1.5, 115 + (pt[1]-crop[1])*1.5)
        points = [xy(q) for q in v['patch_pixels']]
        lo = (min(q[0] for q in points)-12, min(q[1] for q in points)-12)
        hi = (max(q[0] for q in points)+12, max(q[1] for q in points)+12)
        draw.ellipse((*lo, *hi), outline='#ffc04a', width=3)
        path = [xy(q) for q in v['inside_path_pixels']]
        draw.line(path, fill='#ffc04a', width=3)
        draw.line((lo[0], hi[1], x+50, 610), fill='#ffc04a', width=2)
        draw.text((x+15, 620), '橙色为内部发片的投影位置，原渲染未改变', font=small, fill='#ffdc96')
draw.text((25, 680), f"已确认连片范围 {v['maximum_embedded_span_cm']:.2f} cm，最深 {v['maximum_depth_cm']:.2f} cm；28条相邻边均在身体内部。", font=font, fill='white')
draw.text((25, 718), '该问题属于沿用旧物理的刘海；两束新代理未超5厘米。仅算至7.73秒，11秒和12.5秒尚未验证。', font=small, fill='#bccada')
figure = run / '完整头发_停止位置复查.jpg'
sheet.save(figure, quality=95)

caches = []
for path in sorted((run / 'cache').glob('*.pc2')):
    with path.open('rb') as f:
        magic, version, count, start, step, frames = struct.unpack('<12siiffi', f.read(32))
    assert magic == b'POINTCACHE2\0' and path.stat().st_size == 32 + count*frames*12
    caches.append(dict(file=str(path), points=count, start=start, step=step, samples=frames, bytes=path.stat().st_size))
for q in caches:
    if Path(q['file']).name.startswith('SideSurface_'):
        assert q['samples'] == r['frames'][1]
records = []
cards = []
for frame in [1, 201, 226, v['frame']]:
    path = run / 'keyframes' / f'f{frame:04d}.png'
    with Image.open(path) as im:
        im.verify()
    records.append(dict(frame=frame, seconds=(frame-1)/30, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    cards.append(f'<article><h2>{(frame-1)/30:.2f}秒 · 帧{frame}</h2><a href="keyframes/{path.name}"><img src="keyframes/{path.name}"></a></article>')
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>完整头发·原生薄面物理停止复查</title><style>body{background:#111b29;color:#e9f1ff;margin:24px;font:17px/1.6 system-ui,"Microsoft YaHei"}h1{font-size:25px}img{width:100%;max-width:1440px}a{color:#b9d5ff}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}article{background:#1d2a3c}h2{font-size:18px;padding:8px}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><h1>完整头发 · 原生薄面代理本轮复查</h1><p>两束短侧发采用 Blender 自带 Cloth Dynamics 薄面物理，通过原生 Surface Deform 带动原始发片。其他头发沿用旧物理，全部保持正常材质与完整角色。</p><p>STATUS</p><p>埋入范围或深度任一超过5厘米才处理。范围是同一连通埋入片段的最大空间跨度，不是穿入深度。本轮未生成视频，也没有完成5–15秒图集。</p><img src="完整头发_停止位置复查.jpg"><p><a href="完整角色_两侧薄面原生物理_复查.blend">新工程（仅缓存1–233帧）</a> · <a href="threshold_patch_verification.json">独立复核数据</a> · <a href="review_manifest.json">本轮输出清单</a></p><div class="grid">CARDS</div></html>'''
description = f"已停止于 {v['original_seconds']:.2f}秒：左侧刘海 FrontHair5-1.L 穿入左上臂，连片范围 {v['maximum_embedded_span_cm']:.2f}厘米，最深 {v['maximum_depth_cm']:.2f}厘米；28/28相邻边在身体内部。两束新代理此刻均未超5厘米。11秒和12.5秒尚未验证。"
(run / '查看本轮复查.html').write_text(page.replace('STATUS', html.escape(description)).replace('CARDS', ''.join(cards)), 'utf8')
manifest = dict(status='STOPPED_ON_CONFIRMED_USER_5CM_LIMIT', description=description, blend=r['blend'], cached_frames=r['frames'], video_generated=False, complete_gallery_generated=False, fixed_camera=True, resolution=[1920,1080], all_hair_collision_solved=False, geometry_transfer=r['geometry_transfer'], physics=r['physics'], all_over_limit_patches=v['all_over_limit_patches'], side_surface_display_contacts=v['side_surface_display_contacts'], caches=caches, normal_stills=records, pending_times_seconds=[11,12.5,15], shutdown_forbidden=True)
(run / 'review_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf8')
(run / '本轮说明.txt').write_text(description+'\n原工程和原始数据保留；身体、腕部和抱手动作未改变。当前PC2为显示回放缓存，不能作为求解器继续模拟的状态。禁止自动关机。\n', 'utf8')
print(json.dumps(dict(gallery=str(run/'查看本轮复查.html'),figure=str(figure),description=description,caches_valid=True),ensure_ascii=False))
