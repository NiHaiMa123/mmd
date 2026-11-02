"""Normal character stills and data annotations for the classic Cloth stop."""
import argparse,json,html
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run=Path(a.run)
r=json.loads((run/'result.json').read_text('utf8'));v=json.loads((run/'stopped_review.json').read_text('utf8'))
assert v['all_27_native_pin_groups_valid'] and v['body_error_m']<5e-6
fontpath=r'C:\Windows\Fonts\msyh.ttc';font=ImageFont.truetype(fontpath,22);small=ImageFont.truetype(fontpath,19);title=ImageFont.truetype(fontpath,29)
sheet=Image.new('RGB',(1440,800),'#111c2b');draw=ImageDraw.Draw(sheet)
draw.text((25,18),'完整头发 · 经典Cloth基线 · 显示发片局部拉伸后停止',font=title,fill='white')
crop=(700,105,1150,465)
for x,frame,label in [(25,1,'初始帧：完整头发，正常材质'),(740,v['frame'],'第7帧（0.20秒）：橙圈标出局部变形位置')]:
 path=run/'keyframes'/f'f{frame:04d}.png'
 with Image.open(path) as im:
  assert im.size==(1920,1080);sheet.paste(im.convert('RGB').crop(crop).resize((675,540),Image.Resampling.LANCZOS),(x,112))
 draw.text((x,74),label,font=small,fill='white')
 if frame>1:
  points=[(x+(q[0]-crop[0])*1.5,112+(q[1]-crop[1])*1.5) for q in v['edge_pixels']];centre=tuple(sum(q[i] for q in points)/2 for i in range(2))
  draw.ellipse((centre[0]-20,centre[1]-20,centre[0]+20,centre[1]+20),outline='#ffbd55',width=3)
  draw.line((centre[0]+20,centre[1]+20,x+490,605),fill='#ffbd55',width=2)
  draw.text((x+270,614),'正面投影较短，三维网格边有拉长',font=small,fill='#ffda9b')
draw.text((25,681),f"局部显示网格边：{v['initial_edge_m']*1000:.2f} → {v['stopped_edge_m']*1000:.2f} mm；同束物理代理边长P99约 {v['proxy']['edge_ratio_p01_p99'][1]:.3f} 倍。",font=font,fill='white')
draw.text((25,724),'27束均已接入经典Cloth；根固定正常、身体未改。证据指向Surface Deform传递放大。',font=small,fill='#b5c8df')
draw.text((25,760),'目前只验证至第7帧，7.5秒、11秒、12.5秒及5–15秒图集尚未完成。',font=small,fill='#b5c8df')
figure=run/'完整头发_经典Cloth_停止复查.jpg';sheet.save(figure,quality=95)
description=f"经典Cloth对照在第{v['frame']}帧（{v['seconds']:.2f}秒）停止。右短侧发Sidehair1.R一条实际网格边从{v['initial_edge_m']*1000:.2f}毫米变为{v['stopped_edge_m']*1000:.2f}毫米；此刻没有检测到身体埋入，停止原因是局部显示发片拉伸。"
rows=''.join('<tr><td>'+html.escape(q['chain'])+'</td><td>'+f"{q['edge_ratio_p01_p99'][0]:.4f}–{q['edge_ratio_p01_p99'][1]:.4f}"+'</td><td>'+f"{q['maximum_edge_extension_m']*1000:.3f} mm"+'</td></tr>' for q in v['all_proxy_results'])
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全头经典Cloth停止复查</title><style>body{background:#111c2b;color:#eaf2ff;font:17px/1.65 system-ui,"Microsoft YaHei";padding:24px;max-width:1450px;margin:auto}a{color:#a5d1ff}img{width:100%}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #475c75;padding:8px;text-align:left}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><h1>完整头发：经典Cloth对照已停止</h1><p>DESCRIPTION</p><p>代理共27束、5260点、9866面，全部使用经典Cloth，根区采用原生Pin Group；原始发片由Surface Deform带动。身体逐帧保持原轨迹，抱手动作数据未改，正常材质与完整头发保留。发束自碰和互碰未启用，本轮仅验证身体外碰及显示变形。</p><img src="完整头发_经典Cloth_停止复查.jpg"><p>重新打开缓存工程后复核：同束代理边长P99约1.026倍，最大单边延长约2.46毫米，而实际显示发片局部延长约20.97毫米。显示传递放大是下一步重点排查方向；不能据此断言经典Cloth本身发生全头失稳。</p><p>首次接入中“组名先赋值、组后创建”的接口错误已通过独立小对象复现并修复。旧错误配置结果保留并明确标记无效。本页是修复接口后的真实停止结果，未盲目调整参数继续试算。</p><p>按用户约定暂停新的物理模拟。建议下一步采用已核对的<a href="https://www.bilibili.com/video/BV1pS9MB8Em2?t=147">社区发骨跟踪流程（02:27–03:12）</a>，保留原网格权重，减少直接表面绑定对原始发片局部形状的影响。这个替代映射尚未实施。</p><p>当前工程和27束有效PC2回放缓存仅覆盖1–7帧，不能恢复为完整求解器状态。7.5秒、11秒、12.5秒未验证；5–15秒图集未完成。自动关机仍取消。</p><p><a href="完整角色_全头经典Cloth_复查.blend">新工程</a> · <a href="stopped_review.json">独立复核</a> · <a href="setup.json">物理参数</a></p><div class="grid"><a href="keyframes/f0001.png"><img src="keyframes/f0001.png"></a><a href="keyframes/f0007.png"><img src="keyframes/f0007.png"></a></div><details><summary>全部27束代理的停止帧边长数据</summary><table><tr><th>发束</th><th>边长P01–P99比</th><th>最大边延长</th></tr>ROWS</table></details></html>'''.replace('DESCRIPTION',html.escape(description)).replace('ROWS',rows)
(run/'查看全头经典Cloth复查.html').write_text(page,'utf8')
report=dict(status='STOPPED_ON_ACTUAL_DISPLAY_STRETCH',description=description,frames=r['frames'],blend=r['blend'],review=str(run/'查看全头经典Cloth复查.html'),figure=str(figure),cached_proxy_count=27,valid_cache_files=len(v['verified_cache_headers']),all_original_materials=True,all_hair_shown=True,all_hair_collision_solved=False,next_step_not_executed='Community proxy-to-bone tracking with original skin weights',shutdown_forbidden=True)
(run/'review_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False))
