"""Launch a bounded, nested comparison with the unmodified Jiggle solver."""
import bpy,json,subprocess,hashlib
from pathlib import Path
repo=Path(r'E:\project\mmd\mmd_repo');root=repo.parent/'work/headswap_xl_codex/jiggle_naturalness_fix_20261102';root.mkdir(exist_ok=True)
blender=r'D:\software\blender\5.2.1\blender.exe';jobs=[]
common=['--fit-groom-bones','--fit-radius','--pin-root-segments','--front-root-count','2','--preroll','60','--simulation-fps','120','--last','450','--colliders','ellipsoids']
for name,radius,roots in [('A_ellipsoids_only',1.,2),('B_smaller_radius',.5,2),('C_shorter_root',.5,1)]:
 out=root/name;out.mkdir(exist_ok=True);assert not (out/'bake_report.json').exists(),('Completed trial preserved',name)
 argv=[blender,'--background','--factory-startup','--threads','4','--python',str(repo/'scripts/run_jiggle_hair_candidate.py'),'--','--out',str(out),*common,'--radius-scale',str(radius),'--root-segment-count',str(roots)]
 jobs.append(dict(key='jiggle_naturalness_'+name+'01',log=root/(name+'.log'),argv=argv))
for job in jobs:
 old=bpy.app.driver_namespace.get('MMD_BACKGROUND_'+job['key']);assert old is None or old.poll() is not None,('Already running',job['key'])
records=[]
for job in jobs:
 with job['log'].open('ab') as stream:proc=subprocess.Popen(job['argv'],stdout=stream,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
 bpy.app.driver_namespace['MMD_BACKGROUND_'+job['key']]=proc
 records.append(dict(key=job['key'],argv=job['argv'],log=str(job['log']),pid=proc.pid,launcher='Blender MCP',desktop_input=False))
plan=dict(baseline='jiggle_physics_20261031/candidate13',full_head_chains=27,original_body_and_hug_motion_preserved=True,upstream_solver_modified=False,frames=[1,450],scene_preparation_script_sha256=hashlib.sha256((repo/'scripts/run_jiggle_hair_candidate.py').read_bytes()).hexdigest(),comparisons=['Baseline toA: remove mesh collider, retain17ellipsoids','A toB: multiply all fitted hair collision radii by0.5','B toC: change non-fringe fixed root segment count2to1; fringe retains2'],new_per_frame_corrective_motion=False,shutdown_forbidden=True,jobs=records)
(root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf8');print(json.dumps([dict(key=j['key'],pid=j['pid']) for j in records],ensure_ascii=False))
