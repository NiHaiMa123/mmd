import bpy,json,subprocess
from pathlib import Path
out=Path(r'E:\project\mmd\work\headswap_xl_codex\standard_proxy_20261031');out.mkdir(parents=True,exist_ok=True)
key='MMD_BACKGROUND_standard_proxy_inspect';old=bpy.app.driver_namespace.get(key)
assert old is None or old.poll() is not None,'Inspection already running'
with (out/'inspection.log').open('ab') as log:
    job=subprocess.Popen([bpy.app.binary_path,'-b','-t','8','--python',r'E:\project\mmd\mmd_repo\scripts\inspect_standard_proxy_inputs.py'],stdout=log,stderr=subprocess.STDOUT,cwd=r'E:\project\mmd\mmd_repo',creationflags=subprocess.CREATE_NO_WINDOW)
bpy.app.driver_namespace[key]=job
(out/'inspection_job.json').write_text(json.dumps(dict(pid=job.pid,stage='READ_ONLY_INSPECTION',launcher='Blender MCP',desktop_input=False),indent=2),'utf8');print(job.pid)
