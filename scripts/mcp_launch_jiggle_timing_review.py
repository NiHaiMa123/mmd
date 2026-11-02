"""Review baked output only; do not start further dynamics."""
import bpy
import json
import subprocess
from pathlib import Path
repo = Path(r'E:\project\mmd\mmd_repo')
root = repo.parent / 'work/headswap_xl_codex/jiggle_timing_trace_20261102'
assert not (root / 'review_jobs.json').exists(), 'Review already launched; inspect existing jobs'
active = [k for k, v in bpy.app.driver_namespace.items() if k.startswith(('MMD_BACKGROUND_', 'HEADLESS_')) and hasattr(v, 'poll') and v.poll() is None]
assert not active, active
blender = r'D:\software\blender\5.2.1\blender.exe'
common = [blender, '--background', '--factory-startup', '--threads', '4', '--python']
jobs = [dict(key='MMD_BACKGROUND_jiggle_timing_mesh_review01', log=str(root / 'mesh_review.log'),
             argv=common + [str(repo / 'scripts/review_jiggle_timing_mesh.py')])]
frames = '1,226,301,331,343,344,345,356,362,363,376,391'
for fps in [30, 120]:
    folder = root / f'{fps}Hz'
    source = json.loads((folder / 'bake_report.json').read_text(encoding='utf-8'))['blend']
    jobs.append(dict(key=f'MMD_BACKGROUND_jiggle_timing_depth_{fps}Hz01', log=str(folder / 'depth.log'),
                     argv=common + [str(repo / 'scripts/measure_full_hair_intrusion.py'), '--', '--source', source,
                                    '--out', str(folder / 'depth_keyframes'), '--frames', frames, '--capture-motion']))
for job in jobs:
    with Path(job['log']).open('ab') as stream:
        process = subprocess.Popen(job['argv'], stdout=stream, stderr=subprocess.STDOUT,
                                   cwd=str(repo), creationflags=subprocess.CREATE_NO_WINDOW)
    bpy.app.driver_namespace[job['key']] = process
    job['pid'] = process.pid
    job['new_simulation'] = False
(root / 'review_jobs.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps([dict(key=j['key'], pid=j['pid']) for j in jobs]))
