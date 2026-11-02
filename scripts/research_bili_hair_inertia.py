"""Read selected original tutorials through the repaired Bilibili project."""
import json,sys
from pathlib import Path
sys.dont_write_bytecode=True;sys.path.insert(0,r'E:\project\bilibili\src')
from bilibili_agent.config import load_config
from bilibili_agent.pipeline import Pipeline
root=Path(r'E:\project\mmd\work\hair_inertia_research_20261102');pipe=Pipeline(load_config(root/'bili_research.toml'))
targets=['BV1mY4y1c7mx','BV15itbzbEfP','BV1qpd1B8EF9','BV1MS9jBaEXu','BV1xE421w7dC'];rows=[]
try:
 for target in targets:
  print('INERTIA_FETCH_BEGIN',target,flush=True)
  value=pipe.fetch(target,parts=[1],mode='subtitle',subtitle_source='platform').to_dict();rows.append(value)
  (root/'selected_fetch.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
  print('INERTIA_FETCH',json.dumps(value,ensure_ascii=False),flush=True)
  err=value.get('error') or {}
  if err.get('error_code') in [412,429,-412,-352]:break
finally:pipe.close()
