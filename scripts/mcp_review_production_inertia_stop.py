"""Read-only actual mesh review and normal full-character stills after a stop."""
import bpy,json,subprocess
from pathlib import Path
run=Path(r'E:\project\mmd\work\headswap_xl_codex\inertia_control_20261102\production_soft_rear02');repo=Path(r'E:\project\mmd\mmd_repo');blender=r'D:\software\blender\5.2.1\blender.exe'
r=json.loads((run/'result.json').read_text('utf8'));assert r['stop'] and r['stop'].get('stretched_chains');last=r['frames'][1]
jobs=[dict(key='production_inertia_stop_mesh_review02',log=run/'mesh_review.log',argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/review_classic_full_hair_stop.py'),'--','--run',str(run)]),dict(key='production_inertia_stop_render02',log=run/'review_render.log',argv=[blender,'--background','--factory-startup','--threads','8','--python',str(repo/'scripts/render_full_hair_showcase.py'),'--','--source',r['blend'],'--out',str(run/'keyframes'),'--frames',','.join(str(f) for f in sorted(set([1,max(1,last-15),max(1,last-5),last]))),'--samples','24','--device','GPU']),dict(key='production_inertia_stop_depth02',log=run/'depth_review.log',argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/measure_full_hair_intrusion.py'),'--','--source',r['blend'],'--out',str(run/'independent_intrusion'),'--frames',str(last)])]
for job in jobs:
 old=bpy.app.driver_namespace.get('MMD_BACKGROUND_'+job['key']);assert old is None or old.poll() is not None,('Already running',job['key'])
records=[]
for job in jobs:
 with job['log'].open('ab') as log:process=subprocess.Popen(job['argv'],stdout=log,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
 bpy.app.driver_namespace['MMD_BACKGROUND_'+job['key']]=process
 records.append(dict(key=job['key'],log=str(job['log']),argv=job['argv'],pid=process.pid,launcher='Blender MCP',simulation_started=False,desktop_input=False))
(run/'review_jobs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf8');print(json.dumps(records,ensure_ascii=False))
