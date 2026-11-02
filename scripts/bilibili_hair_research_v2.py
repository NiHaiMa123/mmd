"""Use the user's Bilibili pipeline; write all outputs inside this workspace."""
import sys,json,argparse
from pathlib import Path
sys.dont_write_bytecode=True
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8')
sys.path.insert(0,'E:/project/bilibili/src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline
from bilibili_agent.explore import explore
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['search','inspect','fetch']);parser.add_argument('targets',nargs='*');parser.add_argument('--round',default='1');parser.add_argument('--source',default='platform');a=parser.parse_args()
root=Path(__file__).resolve().parents[1]/'outputs/bilibili_hair_research_20261028';root.mkdir(exist_ok=True);config=load_config('E:/project/bilibili/config.toml');config.output_dir=str(root/'videos');config.media_cache=str(root/'media');config.temp_dir=str(root/'tmp');pipe=Pipeline(config)
try:
 if a.mode=='search':
  queries=a.targets or [{'query':'MMD 头发 刚体 穿模','axis':'MMD collider setup'},{'query':'MMD 头发 刚体 拉伸 爆炸','axis':'instability and pinning'},{'query':'Blender 发片 物理 顶点组','axis':'polygon hair pinning'},{'query':'Blender 头发 布料 碰撞','axis':'surface hair collision'},{'query':'MMD 摸头 头发 穿模 修正','axis':'hand contact intent'},{'query':'Blender XPBD 头发 动力学','axis':'native XPBD setup'},{'query':'MMD 刚体 物理演算组 非碰撞组 头发','axis':'collision group filtering'},{'query':'Blender 头发 骨骼 物理 Wiggle','axis':'bone backend'}]
  result=explore(pipe.search_provider,queries,per_query=10,max_queries=8,limit=30);(root/f'search_{a.round}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('BILI_HAIR_SEARCH',json.dumps({k:result.get(k) for k in ('status','count','completed_queries','error')},ensure_ascii=False),flush=True)
  for row in result['results']:print(json.dumps({k:row.get(k) for k in ('bvid','title','author','description','duration_sec')},ensure_ascii=False),flush=True)
 else:
  rows=[]
  for target in a.targets:
   result=pipe.inspect(target).to_dict() if a.mode=='inspect' else pipe.fetch(target,parts=[1],mode='subtitle',subtitle_source=a.source).to_dict();rows.append(result);(root/f'{a.mode}_{a.round}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
   if (result.get('error') or {}).get('error_code') in (412,429,-412,-352):break
finally:pipe.close()
