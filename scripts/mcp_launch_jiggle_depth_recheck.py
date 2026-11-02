"""Launch two read-only depth partitions and one GPU review of the existing bake."""
import bpy,json,subprocess
from pathlib import Path
repo=Path(r'E:\project\mmd\mmd_repo');root=repo.parent/'work/headswap_xl_codex/jiggle_recheck_5cm_20261102';setup=json.loads((root/'prepared/setup.json').read_text('utf8'));assert setup['status']=='EXISTING_JIGGLE_BAKE_REOPEN_VERIFIED';blender=r'D:\software\blender\5.2.1\blender.exe'
jobs=[]
for name,first,last in [('depth_A',1,225),('depth_B',226,450)]:
 out=root/name;out.mkdir(exist_ok=True)
 jobs.append(dict(key='jiggle_recheck_'+name+'01',log=root/(name+'.log'),argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/measure_full_hair_intrusion.py'),'--','--source',setup['blend'],'--out',str(out),'--frames',','.join(map(str,range(first,last+1))),'--capture-motion']))
jobs.append(dict(key='jiggle_recheck_render01',log=root/'render.log',argv=[blender,'--background','--factory-startup','--threads','8','--python',str(repo/'scripts/render_baked_hair_review.py'),'--','--source',setup['blend'],'--out',str(root/'review'),'--start-seconds','10','--duration','3','--fps','24','--samples','24','--half-second-gallery']))
for job in jobs:
 old=bpy.app.driver_namespace.get('MMD_BACKGROUND_'+job['key']);assert old is None or old.poll() is not None,('Already running',job['key'])
records=[]
for job in jobs:
 with job['log'].open('ab') as stream:proc=subprocess.Popen(job['argv'],stdout=stream,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
 bpy.app.driver_namespace['MMD_BACKGROUND_'+job['key']]=proc
 records.append(dict(key=job['key'],argv=job['argv'],log=str(job['log']),pid=proc.pid,launcher='Blender MCP',new_simulation=False,desktop_input=False))
(root/'jobs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf8');print(json.dumps([dict(key=r['key'],pid=r['pid'],log=r['log']) for r in records],ensure_ascii=False))
