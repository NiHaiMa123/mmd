"""One new root-policy trial with no collisions; all other dynamics remain the same."""
import bpy
import hashlib
import json
import subprocess
from pathlib import Path

repo = Path(r'E:\project\mmd\mmd_repo')
base = repo.parent / 'work/headswap_xl_codex'
root = base / 'jiggle_root_point_20261102'
root.mkdir(exist_ok=True)
assert not (root / 'launch.json').exists(), 'Already launched: inspect existing status instead'
active = [k for k,v in bpy.app.driver_namespace.items() if k.startswith(('MMD_BACKGROUND_','HEADLESS_')) and hasattr(v,'poll') and v.poll() is None]
assert not active, ('Existing background jobs',active)
meta = json.loads((base / 'standard_proxy_20261031/inspection/inputs.json').read_text(encoding='utf-8'))
indices = list(range(7,23))+[25,26]
chains = [meta['chains'][i]['name'] for i in indices]
policy = root / 'long_hair_root_policy.json'
policy.write_text(json.dumps(chains,ensure_ascii=False,indent=2),encoding='utf-8')
argv = [r'D:\software\blender\5.2.1\blender.exe','--background','--factory-startup','--threads','4',
        '--python',str(repo / 'scripts/run_jiggle_free_head_turn.py'),'--','--out',str(root),'--free-root-chains',str(policy)]
key = 'MMD_BACKGROUND_jiggle_root_point_trial01'
with (root / 'worker.log').open('ab') as stream:
    process = subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT,cwd=str(repo),creationflags=subprocess.CREATE_NO_WINDOW)
bpy.app.driver_namespace[key] = process
record = dict(key=key,pid=process.pid,argv=argv,changed='Only enable first two formerly fixed bones on18long chains; root elasticity stays1, all collisions remain off',
              plugin_solver_modified=False,new_per_frame_correctives=False,chains=chains,
              baseline=str(base / 'jiggle_free_motion_20261102'),worker_sha256=hashlib.sha256((repo / 'scripts/run_jiggle_free_head_turn.py').read_bytes()).hexdigest(),shutdown_forbidden=True)
(root / 'launch.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(pid=process.pid,key=key,chains=len(chains)),ensure_ascii=False))
