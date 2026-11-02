"""Use the local bilibili-agent project; keep all new research output here."""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,r'E:\project\bilibili\src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline
from bilibili_agent.explore import explore
from bilibili_agent.bili_api import BiliApiError
ROOT=Path(__file__).resolve().parents[1]/'outputs/bilibili_cloth_research_20261024'


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['explore','inspect','fetch'])
    p.add_argument('targets',nargs='*');p.add_argument('--source',default='platform');p.add_argument('--round',default='1')
    p.add_argument('--parts',type=int,nargs='+',default=[1]);p.add_argument('--mode',default='subtitle')
    p.add_argument('--max-images',type=int,default=12)
    a=p.parse_args();ROOT.mkdir(parents=True,exist_ok=True)
    cfg=load_config(r'E:\project\bilibili\config.toml')
    cfg.output_dir=str(ROOT/'videos');cfg.media_cache=str(ROOT/'media');cfg.temp_dir=str(ROOT/'tmp')
    cfg.max_images=a.max_images
    pipe=Pipeline(cfg)
    try:
        if a.action=='explore':
            queries=['MMD 宽袖 物理','MMD 袖子 穿模','PMXEditor 袖子 刚体','MMD 飘带 物理',
                     'PMXEditor 碰撞组 穿模','blender 宽袖 布料','blender MMD 刚体 布料','MMD 布料 烘焙 骨骼'] if not a.targets else a.targets
            report=explore(pipe.search_provider,queries,per_query=15,max_queries=12,limit=30)
            (ROOT/f'explore_{a.round}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
            print(json.dumps({'status':report['status'],'count':report['count'],'runs':report['query_runs'],'error':report['error']},ensure_ascii=False),flush=True)
            for item in report['results']:
                print(json.dumps({k:item.get(k) for k in ('bvid','title','author','duration_s','description')},ensure_ascii=False),flush=True)
            if report['error']:raise SystemExit(1)
        else:
            reports=[]
            for target in a.targets:
                if a.action=='inspect':
                    info=pipe.inspect(target)
                    report=info.to_dict()
                else:
                    report=pipe.fetch(target,parts=a.parts,mode=a.mode,subtitle_source=a.source).to_dict()
                reports.append(report)
                print(json.dumps({k:v for k,v in report.items() if k!='parts'},ensure_ascii=False),flush=True)
                (ROOT/f'{a.action}_{a.round}.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
                error=report.get('error') or {}
                if error.get('error_code') in (412,429,-412,-352):raise SystemExit(1)
    except BiliApiError as exc:
        print(json.dumps(exc.to_dict(),ensure_ascii=False),flush=True);raise SystemExit(1)
    finally:pipe.close()


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf8')
    main()
