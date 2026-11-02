"""Launch only the explicit standard-proxy job; keep the GUI untouched."""
import bpy,json,subprocess
from pathlib import Path
root=Path(r'E:\project\mmd\work\headswap_xl_codex\standard_proxy_20261031')
config=json.loads((root/'next_job.json').read_text('utf8'));key='MMD_BACKGROUND_standard_proxy_'+config['key'];old=bpy.app.driver_namespace.get(key)
assert old is None or old.poll() is not None,'This standard-proxy task is already running'
with Path(config['log']).open('ab') as log:
    job=subprocess.Popen(config['argv'],stdout=log,stderr=subprocess.STDOUT,cwd=r'E:\project\mmd\mmd_repo',creationflags=subprocess.CREATE_NO_WINDOW)
bpy.app.driver_namespace[key]=job
record=dict(config,pid=job.pid,launcher='Blender MCP',desktop_input=False)
(root/(config['key']+'_job.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))
