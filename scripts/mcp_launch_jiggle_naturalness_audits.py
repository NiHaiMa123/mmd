"""Read-only motion and complete-head target-frame audits, no new dynamics."""
import bpy,json,subprocess
from pathlib import Path
repo=Path(r'E:\project\mmd\mmd_repo');root=repo.parent/'work/headswap_xl_codex/jiggle_naturalness_fix_20261102';blender=r'D:\software\blender\5.2.1\blender.exe';jobs=[]
frames=sorted(set(list(range(301,392))+[1,151,211,226,242,244,256,280,300,450]));jobs.append(dict(key='jiggle_naturalness_motion01',log=root/'motion_review.log',argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/measure_jiggle_naturalness_trials.py'),'--','--root',str(root)]))
for name in ['A_ellipsoids_only','B_smaller_radius','C_shorter_root']:
 out=root/name;report=json.loads((out/'bake_report.json').read_text('utf8'));assert report['frames']==[1,450] and report['body_bone_max_error']==0
 jobs.append(dict(key='jiggle_naturalness_depth_'+name+'01',log=out/'depth.log',argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/measure_full_hair_intrusion.py'),'--','--source',report['blend'],'--out',str(out/'depth_target'),'--frames',','.join(map(str,frames)),'--capture-motion']))
for job in jobs:
 old=bpy.app.driver_namespace.get('MMD_BACKGROUND_'+job['key']);assert old is None or old.poll() is not None,('Already running',job['key'])
records=[]
for job in jobs:
 with job['log'].open('ab') as stream:proc=subprocess.Popen(job['argv'],stdout=stream,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
 bpy.app.driver_namespace['MMD_BACKGROUND_'+job['key']]=proc;records.append(dict(key=job['key'],pid=proc.pid,log=str(job['log']),argv=job['argv'],launcher='Blender MCP',new_simulation=False))
(root/'audit_jobs.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf8');print(json.dumps([dict(key=r['key'],pid=r['pid']) for r in records],ensure_ascii=False))
