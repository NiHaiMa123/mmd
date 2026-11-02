"""Publish bounded, source-linked research; candidates are not viewing claims."""
import html,json
from pathlib import Path

root=Path(r'E:\project\mmd\work\hair_community_research_20261101')
esc=html.escape
pool={}
rounds=[]
for name in ['search_round1.json','search_round2.json']:
 r=json.loads((root/name).read_text('utf8'));assert r['ok'] and r['completed_queries']==8
 rounds.append(dict(file=name,queries=r['query_runs']))
 for row in r['results']:
  if row['bvid'] not in pool:pool[row['bvid']]=row
  else:pool[row['bvid']]['matches']+=row['matches']

# Bounded paraphrases, each tied to actually read video content or frames.
videos=[
 ('BV16rzpBcEFT','Paper朱','无需插件的MMD头发和服装物理','03:21、04:31–05:10','平台AI字幕（复用已生成产物）','以阻尼追踪的影响控制摆动，刘海取更小影响；这不是对完整网格防穿模的证明。',r'E:\project\bilibili\output\BV16rzpBcEFT\P01_35535782015\transcript.md'),
 ('BV1cD4y1R7U9','Sextet','用布料模拟头发物理','01:35、03:15、06:30、07:30','实际操作帧；平台字幕只有歌曲歌词','独立头发模拟网格带动发骨，另制身体局部碰撞网格。已看9张操作帧。不能用背景歌词解释操作。',str(root/'sextet_visual_evidence/manifest.json')),
 ('BV1pS9MB8Em2','启辰_TB','有物理又可控的头发','02:27–03:12、03:45–04:11、04:45','画面OCR+Qwen3-ASR；77%时间覆盖，incomplete','经典Cloth固定根组，追踪骨骼读取代理顶点组；另一套控制骨骼复制旋转，允许人工调节。已核对03:05及03:45画面。',None),
 ('BV1JTx46CEqT','MiaoBox','MMD物理优化插件2.0','00:06–00:36、01:00–01:25','平台AI字幕+关键帧','把绑定错误和参数问题分开；一键功能主要简化参数并重新烘焙，以改善乱抖乱飞，不负责修复任意错误绑定。',None),
 ('BV1PZ421T7Yj','MiaoBox','MMD物理模拟机制与雷区','02:18–02:58、03:20–05:15、06:40–07:44','平台AI字幕','MMD是刚体带动骨骼，需连续逐帧烘焙；改动动作后需重新计算。示例排查刚体模式。',None),
 ('BV1Bi1HBTELx','KafeiMMD','新版MMD桥含物理VMD流程','01:45–02:19、03:53–04:06、04:36–05:48','平台AI字幕','先修名称/编码与模型预设，原生MMD桥烘焙含物理VMD再导入Blender。04:38仍要求处理动作穿模；桥是传输/烘焙流程，不是万能修复器。',None),
 ('BV1CK411Q7UY','异次元学者','PMX流程头发问题修复','01:27–05:27、09:50–11:53、11:57–12:55','平台AI字幕','排查Root/显示分组、名称编码和换头后残留刚体。这些是转换/记录问题，不等同于连续碰撞算法。字幕所说VMD名称“15字符”应按实际字节编码另核，不能照抄。',None),
 ('BV1Ur421E7Wb','Paper朱','头发抖动与刚体关联','00:35–01:44','平台AI字幕','检查刚体与对应发骨的关联、位置及重复堆叠，而不是只增大阻尼。',None),
 ('BV1UN396fEuy','在下王王玉','自动物理脚本','00:54、01:14–01:34','平台AI字幕及OCR+ASR；后者84%时间覆盖，incomplete','脚本批量设置阻尼追踪及碰撞；演示承认存在局限，并用碰撞参数调整明显穿模。没有独立源码验收或全头保证。',None),
 ('BV1XEoFBbEEH','小峰峰哥l','MMR物理','00:03、02:02','画面OCR+画面；音轨主要为歌曲；另读作者源码','画面包含更新世界与烘焙到骨骼。作者5.2源码使用原生rigidbody_world、关节和骨骼约束，属于MMD刚体工作流，不是新网格级无穿插求解器。',None),
 ('BV19sSUY9EPo','布料力学师','Vellum碰撞体自穿插修复','04:21–05:58、10:49–13:55','平台AI字幕','修复的是身体碰撞体自穿插：一类为可控Blend Shape；另一类把局部碰撞体当布料模拟，其余区域固定。不能误写为直接修复本角色刘海的现成一键方案。',None),
]
evidence=[]
for bvid,author,title,times,kind,finding,local in videos:
 if local is None:
  dirs=list((root/'materialized'/bvid).glob('P*'))
  assert len(dirs)==1
  local=str(dirs[0]/'article.md' if (dirs[0]/'article.md').exists() else dirs[0]/'transcript.md')
 assert Path(local).exists()
 evidence.append(dict(bvid=bvid,author=author,title=title,times=times,evidence=kind,finding=finding,url=f'https://www.bilibili.com/video/{bvid}',local=local))

sources=[
 dict(name='Simplicage 官方文档',url='https://simplicage.readthedocs.io/en/latest/',finding='按网格/骨骼生成Cloth代理和碰撞代理，提供预设和缓存管理。'),
 dict(name='Simplicage 绑定与Pin设置',url='https://simplicage.readthedocs.io/en/latest/settings.html',finding='默认Surface Deform，代理先随骨架再解算；支持Pin权重、影响组和Mesh Deform备用。复杂形状仍可能需要调整。'),
 dict(name='Goo Physics 作者说明',url='https://dillongoo.gumroad.com/l/goo-physics',finding='作者提供Cloth、几何节点、Soft Body等后端，简化碰撞网格及Hair_Fringe/Side/Ponytail预设；页面标注Blender4.1–5.2。作者的生产使用声明尚未在本项目独立验证。'),
 dict(name='Blender 官方2026-10-05开发记录',url='https://code.blender.org/2026/10/geometry-nodes-workshop-september-2026/',finding='节点Cloth仍为实验功能，缺自碰且弯曲约束偏弱；不能将新版等同成熟全头方案。正文open失败，已通过官方域名的搜索索引核对相关段落。'),
 dict(name='MMR 作者5.2实现',url='https://github.com/XiaoFFGe/MikuMikuRig/blob/main/5.2-LTS-MikuMikuRig/addons/MikuMikuRig/operators/Physics.py',finding='已读原生刚体/关节装配、骨骼约束、更新世界与NLA烘焙实现；未安装执行。'),
 dict(name='SideFX Vellum Solver',url='https://www.sidefx.com/docs/houdini/nodes/dop/vellumsolver.html',finding='支持线/三角碰撞、子步、碰撞与最终清理等控制；适合外部角色特效流程，但仍需代理、附着与缓存传递。'),
 dict(name='SideFX Point Deform',url='https://www.sidefx.com/docs/houdini/nodes/sop/pointdeform.html',finding='支持低分辨率代理驱动显示网格；纯线网格的变换可能不稳定，不能将任意中心线直接当可靠面变形笼。'),
 dict(name='SideFX Detangle',url='https://www.sidefx.com/docs/houdini/nodes/sop/detangle.html',finding='现成碰撞修正节点，依赖良好的起始配置。文档含自动禁用/恢复碰撞机制，使用时必须核对，不能将忽略碰撞当修好。'),
 dict(name='Autodesk nHair 碰撞文档',url='https://help.autodesk.com/cloudhelp/2023/ENU/Maya-CharEffEnvBuild/files/GUID-9E4F19DA-86A0-4B7E-97D1-7C6908487693.htm',finding='支持点/边碰撞、自碰、分层及碰撞宽度偏移；文档专门处理跟随毛发超出主动发束边界时的穿入。说明实际显示宽度必须纳入设计。'),
 dict(name='HiPhyEngine 弹性杆文档',url='https://hiphyengine.github.io/material-models/elastic-rod/',finding='支持静置/目标形状、根约束及连续时间碰撞选项，作为候选外部后端；其曲线不穿插不自动证明本角色宽发片不穿插。'),
]
routes=[
 ('原生MMD / MMR / MMD桥','沿用PMX刚体、修关联/碰撞覆盖、连续烘焙骨骼，再进入Blender。','最贴近MMD资产；桥和优化插件不保证任意动作下显示网格无穿模。'),
 ('经典Blender Cloth代理','模拟简洁网格，固定发根，碰撞后带动发骨或原始发片。','社区步骤已找到并核对；与现有新版XPBD应分清，适合作为同场景对照基线。'),
 ('Simplicage','自动生成Cloth代理、Pin/影响组、Surface Deform绑定和缓存。','直接对应当前大量适配工作；需先确认版本和现有复杂分叉的绑定效果。'),
 ('Goo Physics','用现成刘海/侧发/马尾预设，叠加艺术控制及简化碰撞体。','更贴近二次元造型保持需求；作者文档支持5.2，但当前角色效果未试验，未购买。'),
 ('Houdini Vellum','成熟角色特效节点、碰撞清理、代理到显示面传递与缓存。','完整外部后端备选；需要软件环境与资产交换，不是导入就自动修好。'),
 ('Maya nHair','曲线动力学、主动/跟随发束、被动碰撞、碰撞宽度与约束。','同样有代理宽度和显示几何映射问题；现有发片需要适配。'),
 ('HiPhyEngine','现成弹性杆/布料及连续碰撞工具。','补充候选；需验证版本、授权、宽发片映射与实际稳定性，未安装。'),
]
manifest=dict(status='BROAD_SEARCH_AND_SELECTED_CONTENT_REVIEW_COMPLETE',date='2026-11-01',completed_bilibili_queries=16,unique_bilibili_candidates=len(pool),reviewed_videos=len(evidence),candidate_evidence_level='Titles/descriptions only unless listed in reviewed_video_evidence',reviewed_video_evidence=evidence,primary_documentation=sources,routes=routes,queries=rounds,unresolved='No candidate plugin or alternative solver was tested on the current character in this research round.',media_failure='Sextet illustrated BDL download failed to parse; project BiliClient progressive download fallback succeeded and nine real frames were inspected.',new_simulation_started=False,shutdown_forbidden=True)
(root/'research_evidence.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')

def link(url,label):return '<a href="'+esc(url,quote=True)+'" target="_blank">'+esc(label)+'</a>'
def local_href(path):
 p=Path(path)
 try:return p.relative_to(root).as_posix()
 except ValueError:return p.as_uri()
table='<table><thead><tr><th>路线</th><th>已有做法</th><th>对本项目的判断</th></tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in row)+'</tr>' for row in routes)+'</tbody></table>'
cards=[]
for row in evidence:
 cards.append('<article><h3>'+link(row['url'],row['title'])+'</h3><p>'+esc(row['author']+' · '+row['bvid']+' · '+row['times'])+'</p><p class="source">证据：'+esc(row['evidence'])+'</p><p>'+esc(row['finding'])+'</p>'+link(local_href(row['local']),'本地证据')+'</article>')
docs=''.join('<li>'+link(s['url'],s['name'])+'：'+esc(s['finding'])+'</li>' for s in sources)
candidates=''.join('<tr><td>'+link(row['url'],row['bvid'])+'</td><td>'+esc(row['title'])+'</td><td>'+esc(row.get('author') or '')+'</td><td>'+esc(' / '.join(dict.fromkeys(x['query'] for x in row['matches'])))+'</td></tr>' for row in pool.values())
figures=''.join('<figure><img loading="lazy" src="sextet_visual_evidence/t'+str(t).zfill(3)+'.jpg"><figcaption>'+link('https://www.bilibili.com/video/BV1cD4y1R7U9?t='+str(t),f'BV1cD4y1R7U9 · {t//60:02d}:{t%60:02d}')+' · 仅供步骤核对</figcaption></figure>' for t in [195,390])
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MMD头发物理·社区方案调查</title><style>body{background:#111923;color:#e6edf7;font:16px/1.7 system-ui,"Microsoft YaHei";max-width:1300px;margin:auto;padding:26px}a{color:#91c8ff}h1{font-size:28px}h2{margin-top:35px;border-top:1px solid #405269;padding-top:18px}p,li{max-width:1120px}.note{background:#22344a;border-left:4px solid #7bbaff;padding:16px}.cards,.figures{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}article,figure{background:#1c293b;padding:16px;margin:0}article h3{font-size:18px;margin-top:0}.source{font-size:14px;color:#a8bdd8}table{border-collapse:collapse;width:100%;font-size:15px}td,th{border:1px solid #405269;padding:12px;text-align:left;vertical-align:top}img{max-width:100%;display:block}summary{cursor:pointer}details{margin-top:20px}@media(max-width:800px){.cards,.figures{grid-template-columns:1fr}body{padding:14px}table{display:block;overflow-x:auto}}</style><h1>头发物理与穿模：社区现成方案调查</h1><p>2026-11-01 · 16组B站检索 · COUNT条去重候选 · 11条重点视频相关内容复核 · 补充作者源码与官方文档</p><div class="note"><strong>判断：</strong>代理模拟再驱动显示发片是已有路线。当前更需要复用社区的绑定/预设流程，并用成熟后端作完整角色对照；新版节点物理不能仅凭“新”就当作长片最佳方案。</div><h2>对目前卡点的影响</h2><p>现有两束薄面代理仅算至7.73秒；超5厘米的是仍用旧物理的左刘海。这个停止点不能证明两束新代理失败，也不能代表全头通过。当前工程是混合后端，后续应覆盖全部风险发束，而不是每次遇到一束就另造一种算法。</p><p>用户5厘米口径继续有效：同一连片的埋入范围或最深深度任一超过5厘米才处理。诊断与镜头可见效果分别记录，不能用微小误差无限阻塞交付。</p><h2>路线比较</h2>TABLE<h2>推荐的下一步（尚未执行）</h2><ol><li>保留已完成的合法初态、真实根区、完整角色材质和身体动作，把经典Cloth代理流程作为可复现基线，使用同一动作和碰撞体比较7.5秒、11秒、12.5秒；不把所有错误都归为提高子步/增大半径。</li><li>优先核对Simplicage的自动代理/Pin/Surface Deform步骤能否直接替代适配代码；Goo Physics列为更贴近二次元造型保持的现成预设候选。两者未在本角色测试，不能宣称现成即成功。</li><li>全头风险区域采用明确的模拟与显示映射，保留允许局部艺术修正的控制层。先验证完整头发，再按5–15秒每秒两张交付图集；抱手保护和身体动作约束保持。</li><li>若经典后端仍有确认的超限或失稳，按现有约定停止报告，再考虑Vellum等外部后端。不要在同一实验后端上无限微调。</li></ol><h2>重点视频：实际读取了什么</h2><div class="cards">CARDS</div><h2>无技术字幕视频的操作帧复核</h2><p>Sextet视频的平台字幕为背景歌词，原图文下载发生BDL解析错误。改用项目BiliClient取得视频，校验时长并提取9帧；这里仅展示两个核对点，不把歌词当操作说明。</p><div class="figures">FIGURES</div><h2>作者源码与官方文档</h2><ul>DOCS</ul><h2>证据边界</h2><p>搜索命中不等于看过；OCR/ASR时间覆盖不等于技术内容完整。启辰_TB与自动物理脚本的混合字幕仍标记incomplete，引用步骤已结合画面或双方一致的片段核对。MMR即使有声覆盖99%，音轨仍主要是歌曲，机制判断依据实际画面及作者源码。</p><p>现成插件、官方案例都不能替代本角色宽发片与真实身体的验证。HiPhyEngine等连续碰撞保证也不能直接外推到没有被代理覆盖的显示发片。本轮未安装候选插件、未购买、未启动新的角色物理模拟，原文件保留。</p><p>自动关机保持取消。<a href="research_evidence.json">机器可读证据清单</a></p><details><summary>86条候选清单（仅搜索元数据，未逐条观看）</summary><table><tr><th>BV</th><th>标题</th><th>作者</th><th>命中查询</th></tr>CANDIDATES</table></details></html>'''
for key,value in [('COUNT',str(len(pool))),('TABLE',table),('CARDS',''.join(cards)),('FIGURES',figures),('DOCS',docs),('CANDIDATES',candidates)]:page=page.replace(key,value)
(root/'社区头发物理方案调查.html').write_text(page,'utf8')
assert len(pool)==86 and len(evidence)==11
print(json.dumps(dict(report=str(root/'社区头发物理方案调查.html'),candidates=len(pool),reviewed_videos=len(evidence),completed_search_queries=16),ensure_ascii=False))
