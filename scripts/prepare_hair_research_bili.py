"""Reuse the repaired Bilibili CLI; put all new outputs inside MMD workspace."""
import json,sys
from pathlib import Path
sys.path.insert(0,r'E:\project\bilibili\src')
from bilibili_agent.config import load_config

out=Path(r'E:\project\mmd\work\hair_community_research_20261101')
out.mkdir(parents=True,exist_ok=True)
cfg=load_config(r'E:\project\bilibili\config.toml')
tables={k:dict(v) for k,v in cfg.raw.items() if isinstance(v,dict)}
tables.setdefault('paths',{}).update(media_cache=str(out/'media'),output_dir=str(out/'materialized'),temp_dir=str(out/'tmp'))
tables.setdefault('bilibili',{}).update(cookie_file=cfg.cookie_file)
def toml(v):
 if isinstance(v,bool):return 'true' if v else 'false'
 if isinstance(v,str):return json.dumps(v,ensure_ascii=False)
 if isinstance(v,(int,float)):return str(v)
 if isinstance(v,list):return '['+', '.join(toml(x) for x in v)+']'
 raise TypeError(type(v))
lines=[]
for table,values in tables.items():
 lines.append('['+table+']')
 for k,v in values.items():lines.append(k+' = '+toml(v))
 lines.append('')
(out/'bili_research.toml').write_text('\n'.join(lines),'utf8')
queries=[('症状','MMD 头发 穿模 修复'),('原生MMD','PMX 头发 刚体 教程'),('MMD转Blender','Blender MMD 头发 物理'),('发片物理','Blender 头发 布料 物理'),('Blender插件','Blender Wiggle 2 碰撞'),('Houdini','Houdini Vellum 头发 碰撞'),('Maya','Maya nHair 头发 物理'),('成片流程','MMD 物理 烘焙 修正')]
(out/'search_plan.json').write_text(json.dumps(dict(queries=[dict(axis=k,query=q) for k,q in queries]),ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(out=str(out),configuration_ready=True,credentials_printed=False)))
