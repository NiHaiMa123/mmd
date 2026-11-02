"""Run the user's local Bilibili search project, with outputs in this repo."""
import argparse,json,sys
from pathlib import Path
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
sys.dont_write_bytecode=True;sys.path.insert(0,'E:/project/bilibili/src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline
from bilibili_agent.explore import explore
from bilibili_agent.bili_api import BiliApiError
ROOT=Path(__file__).resolve().parents[1]/'outputs/bilibili_contact_research_20261027'
p=argparse.ArgumentParser();p.add_argument('action',choices=['explore','fetch','inspect']);p.add_argument('targets',nargs='*');p.add_argument('--round',default='1');p.add_argument('--source',default='platform');a=p.parse_args();ROOT.mkdir(parents=True,exist_ok=True)
cfg=load_config('E:/project/bilibili/config.toml');cfg.output_dir=str(ROOT/'videos');cfg.media_cache=str(ROOT/'media');cfg.temp_dir=str(ROOT/'tmp');pipe=Pipeline(cfg)
try:
 if a.action=='explore':
  queries=a.targets or ['MMD 动态穿模 动作修正','MMD 手臂 穿胸 修正','blender 人体 自碰撞 动作','blender 防穿模 插件','PPF 布料 解算','HiPhyEngine 穿模','MD 动画 穿模 修复','blender 碰撞 IK 动画']
  result=explore(pipe.search_provider,queries,per_query=10,max_queries=8,limit=32);(ROOT/f'explore_{a.round}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:result.get(k) for k in ('status','count','query_runs','error')},ensure_ascii=False),flush=True)
  for row in result['results']:print(json.dumps({k:row.get(k) for k in ('bvid','title','author','description')},ensure_ascii=False),flush=True)
 else:
  results=[]
  for target in a.targets:
   result=pipe.inspect(target).to_dict() if a.action=='inspect' else pipe.fetch(target,parts=[1],mode='subtitle',subtitle_source=a.source).to_dict();results.append(result);(ROOT/f'{a.action}_{a.round}.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
   error=result.get('error') or {}
   if error.get('error_code') in (412,429,-412,-352):break
except BiliApiError as exc:print(json.dumps(exc.to_dict(),ensure_ascii=False),flush=True)
finally:pipe.close()
