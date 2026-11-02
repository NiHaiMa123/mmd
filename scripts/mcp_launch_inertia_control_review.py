"""Launch the isolated, completed-control review and two cached renders via MCP."""
import bpy,json,subprocess
from pathlib import Path
root=Path(r'E:\project\mmd\work\headswap_xl_codex\inertia_control_20261102');repo=Path(r'E:\project\mmd\mmd_repo');blender=r'D:\software\blender\5.2.1\blender.exe'
for name in ['baseline01','soft_rear01']:
 r=json.loads((root/name/'result.json').read_text('utf8'));assert r['frames']==[1,91] and r['stop'] is None
jobs=[dict(key='inertia_control_review01',log=root/'review_worker.log',argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/review_full_hair_inertia_control.py'),'--','--root',str(root)])]
for name in ['baseline01','soft_rear01']:
 jobs.append(dict(key='inertia_control_render_'+name,log=root/name/'render_worker.log',argv=[blender,'--background','--factory-startup','--threads','6','--python',str(repo/'scripts/render_full_hair_inertia_control.py'),'--','--run',str(root/name)]))
for job in jobs:
 old=bpy.app.driver_namespace.get('MMD_BACKGROUND_'+job['key']);assert old is None or old.poll() is not None,('Already running',job['key'])
records=[]
for job in jobs:
 with job['log'].open('ab') as log:process=subprocess.Popen(job['argv'],stdout=log,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
 bpy.app.driver_namespace['MMD_BACKGROUND_'+job['key']]=process
 records.append(dict(key=job['key'],log=str(job['log']),argv=job['argv'],pid=process.pid,launcher='Blender MCP',desktop_input=False))
(root/'review_render_jobs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf8');print(json.dumps(records,ensure_ascii=False))
