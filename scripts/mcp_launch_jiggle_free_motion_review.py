"""Launch one gravity ablation and render the existing no-collision baseline only."""
import bpy
import json
import subprocess
from pathlib import Path

repo = Path(r'E:\project\mmd\mmd_repo')
root = repo.parent / 'work/headswap_xl_codex/jiggle_free_motion_20261102'
assert not (root / 'review_jobs.json').exists(), 'Existing jobs preserved; inspect progress'
active = [k for k, v in bpy.app.driver_namespace.items() if k.startswith(('MMD_BACKGROUND_', 'HEADLESS_')) and hasattr(v, 'poll') and v.poll() is None]
assert not active, active
receipt = json.loads((root / 'bake_report.json').read_text(encoding='utf-8'))
assert not receipt['strain_flags'] and receipt['no_collision_confirmed_in_every_observed_step']
common = [r'D:\software\blender\5.2.1\blender.exe', '--background', '--factory-startup', '--threads', '4', '--python']
jobs = [dict(key='MMD_BACKGROUND_jiggle_free_gravity_off01', log=str(root / 'gravity_off.log'),
             argv=common+[str(repo / 'scripts/run_jiggle_free_head_turn.py'), '--', '--out', str(root / 'gravity_off'), '--gravity', '0']),
        dict(key='MMD_BACKGROUND_jiggle_free_motion_render01', log=str(root / 'render.log'),
             argv=common+[str(repo / 'scripts/render_baked_hair_review.py'), '--', '--source', receipt['blend'],
                          '--out', str(root / 'continuous_review'), '--start-seconds', '0', '--duration', '3', '--fps', '24', '--samples', '24'])]
for job in jobs:
    with Path(job['log']).open('ab') as stream:
        process = subprocess.Popen(job['argv'], stdout=stream, stderr=subprocess.STDOUT, cwd=str(repo), creationflags=subprocess.CREATE_NO_WINDOW)
    bpy.app.driver_namespace[job['key']] = process
    job['pid'] = process.pid
(root / 'review_jobs.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps([dict(key=j['key'], pid=j['pid']) for j in jobs]))
