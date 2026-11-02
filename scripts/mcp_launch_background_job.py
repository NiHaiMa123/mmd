"""Run an explicit workspace job through Blender MCP, without desktop input."""
import bpy,subprocess,json
from pathlib import Path
P=Path(r'E:\project\mmd\work\headswap_xl_codex\native_mmd_bridge_20261030\headless_bullet');config=json.loads((P/'next_job.json').read_text('utf8'));key='MMD_BACKGROUND_'+config['key'];old=bpy.app.driver_namespace.get(key)
assert old is None or old.poll() is not None,'Existing job still running'
logpath=Path(config['log']);logpath.parent.mkdir(parents=True,exist_ok=True);log=logpath.open('ab')
job=subprocess.Popen(config['argv'],stdout=log,stderr=subprocess.STDOUT,cwd=r'E:\project\mmd\mmd_repo',creationflags=subprocess.CREATE_NO_WINDOW);log.close();bpy.app.driver_namespace[key]=job
record=dict(config,pid=job.pid,input_control='none',launcher='Blender MCP execute_code')
(P/(config['key']+'_job.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print(json.dumps(record,ensure_ascii=False))
