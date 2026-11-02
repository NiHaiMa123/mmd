"""Collect allowed original tutorial frames, with no credentials sent to CDN."""
import json,subprocess,sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
sys.dont_write_bytecode=True;sys.path.insert(0,r'E:\project\bilibili\src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline
root=Path(r'E:\project\mmd\work\hair_inertia_research_20261102');cfg=load_config(root/'bili_research.toml');pipe=Pipeline(cfg)
targets=[('BV1cD4y1R7U9',252426454,[565,570,575,580]),('BV1mY4y1c7mx',806968222,[34,64,99,116,156]),('BV15itbzbEfP',31585861680,[591,621,650,687,727,745,772]),('BV1xE421w7dC',1638730248,[326,334,376,382])]
results=[]
try:
 for bvid,cid,times in targets:
  out=root/'visual_evidence'/bvid;out.mkdir(parents=True,exist_ok=True)
  data=pipe.client.get_json('https://api.bilibili.com/x/player/playurl',params=dict(bvid=bvid,cid=cid,qn=80,fnval=4048,fnver=0,fourk=0))
  if data.get('code')!=0:
   results.append(dict(bvid=bvid,status='API_ERROR',code=data.get('code'),message=data.get('message')))
   if data.get('code') in [412,429,-412,-352]:break
   continue
  payload=data['data'];videos=[v for v in (payload.get('dash') or {}).get('video',[]) if int(v.get('height',0))<=1080]
  if videos:
   selected=max(videos,key=lambda v:(int(v.get('height',0)),v.get('codecid')==7,int(v.get('bandwidth',0))))
   url=selected.get('baseUrl') or selected.get('base_url');height=selected['height'];quality=selected.get('id')
  else:
   stream=payload.get('durl') or [];assert len(stream)==1,'No allowed single stream';url=stream[0]['url'];height=None;quality=payload.get('quality')
  host=urlparse(url).hostname or '';assert host.endswith(('.bilivideo.com','.bilivideo.cn'))
  media=out/'video.mp4'
  if not media.exists():
   with httpx.Client(trust_env=False,timeout=90) as client:
    with client.stream('GET',url,headers={'Referer':'https://www.bilibili.com/','User-Agent':cfg.user_agent},follow_redirects=False) as response:
     response.raise_for_status()
     with media.open('wb') as f:
      for chunk in response.iter_bytes(1024*1024):f.write(chunk)
  frames=[]
  for sec in times:
   target=out/f't{sec:04d}.jpg'
   subprocess.run([cfg.ffmpeg,'-v','error','-y','-ss',str(sec),'-i',str(media),'-frames:v','1','-q:v','2',str(target)],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
   frames.append(dict(seconds=sec,file=str(target)))
  result=dict(bvid=bvid,status='ORIGINAL_FRAMES_READY',height=height,quality=quality,frames=frames);results.append(result)
  (root/'visual_evidence_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8');print('INERTIA_FRAMES',json.dumps(result,ensure_ascii=False),flush=True)
finally:
 pipe.close();(root/'visual_evidence_manifest.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
