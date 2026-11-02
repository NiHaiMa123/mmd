"""Launch a hidden, bounded CPU render from Blender MCP; no desktop input."""
import bpy,subprocess,json
from pathlib import Path
ROOT=Path(r'E:\project\mmd\mmd_repo');P=ROOT.parent/'work/headswap_xl_codex/native_mmd_bridge_20261030/headless_bullet';config=json.loads((P/'next_candidate.json').read_text('utf8')) if (P/'next_candidate.json').exists() else {};OUT=Path(config.get('delivery',str(P/'REVIEW_RAW')))
key='HEADLESS_NORMAL_PREVIEW_RENDER'
previous=bpy.app.driver_namespace.get(key)
assert previous is None or previous.poll() is not None,'An existing preview renderer is still running'
assert json.loads((OUT/'mcp_assembly_status.json').read_text('utf8'))['stage']=='NORMAL_CHARACTER_ASSEMBLED'
args=[r'D:\software\blender\5.2.1\blender.exe','-b','-t','4','--python',str(ROOT/'scripts/render_full_hair_showcase.py'),'--','--source',str(OUT/'完整角色_整头连续物理_15秒.blend'),'--out',str(OUT/config.get('render_folder','keyframes')),'--frames',config.get('frames','1,211,331,336,450'),'--percentage',str(config.get('percentage',100)),'--samples',str(config.get('samples',12)),'--device',config.get('device','CPU')]
log=(OUT/'render.log').open('ab');job=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,cwd=str(ROOT),creationflags=subprocess.CREATE_NO_WINDOW);log.close();bpy.app.driver_namespace[key]=job
(OUT/'render_job.json').write_text(json.dumps(dict(pid=job.pid,args=args,scene='complete normal MMD',input_control='none',device='CPU',threads=4),ensure_ascii=False,indent=2),'utf8');print(json.dumps(dict(started=True,pid=job.pid,log=str(OUT/'render.log'))))
