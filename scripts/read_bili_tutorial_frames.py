"""One-video read-only media fallback for a BDL response parsing failure.

Reuse the repaired project's API/session code, but request a progressive MP4.
No cookie is sent to media CDN. No source project files are changed.
"""
import json,subprocess,sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
sys.path.insert(0,r'E:\project\bilibili\src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline

root=Path(r'E:\project\mmd\work\hair_community_research_20261101')
cfg=load_config(root/'bili_research.toml');pipe=Pipeline(cfg)
out=root/'sextet_visual_evidence';out.mkdir(exist_ok=True)
try:
 data=pipe.client.get_json('https://api.bilibili.com/x/player/playurl',params=dict(bvid='BV1cD4y1R7U9',cid=252426454,qn=64,fnval=1,fnver=0,fourk=0))
 assert data.get('code')==0,('playurl API error',data.get('code'),data.get('message'))
 payload=data['data'];urls=payload.get('durl',[])
 assert len(urls)==1,('Progressive single stream not available',list(payload.keys()))
 url=urls[0]['url'];host=urlparse(url).hostname or ''
 assert host.endswith('.bilivideo.com') or host.endswith('.bilivideo.cn'),host
 path=out/'tutorial.mp4'
 if not path.exists():
  with httpx.Client(trust_env=False,timeout=60) as client:
   with client.stream('GET',url,headers={'Referer':'https://www.bilibili.com/','User-Agent':cfg.user_agent},follow_redirects=False) as response:
    response.raise_for_status()
    with path.open('wb') as f:
     for chunk in response.iter_bytes(1024*1024):f.write(chunk)
 probe=subprocess.run([cfg.ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(path)],check=True,capture_output=True,text=True,encoding='utf8');media=json.loads(probe.stdout)
 assert float(media['format']['duration'])>580
 frames=[]
 for sec in [95,150,195,230,360,390,450,525,550]:
  target=out/f't{sec:03d}.jpg'
  subprocess.run([cfg.ffmpeg,'-v','error','-y','-ss',str(sec),'-i',str(path),'-frames:v','1','-q:v','2',str(target)],check=True,capture_output=True)
  frames.append(dict(seconds=sec,file=str(target)))
 result=dict(status='VISUAL_FRAMES_EXTRACTED',bvid='BV1cD4y1R7U9',platform_subtitles='Background song lyrics; not technical evidence',download='Project BiliClient progressive stream fallback after BDL parsing failed',duration_s=media['format']['duration'],frames=frames)
 (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(json.dumps(result,ensure_ascii=False))
finally:pipe.close()
