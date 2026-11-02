"""Launch one matched two-frequency diagnostic; keep the GUI and old outputs intact."""
import bpy
import hashlib
import json
import subprocess
from pathlib import Path

repo = Path(r'E:\project\mmd\mmd_repo')
root = repo.parent / 'work/headswap_xl_codex/jiggle_timing_trace_20261102'
root.mkdir(exist_ok=True)
assert not (root / 'launch.json').exists(), 'This diagnostic was already launched; inspect its status'
active = [k for k, v in bpy.app.driver_namespace.items()
          if k.startswith(('MMD_BACKGROUND_', 'HEADLESS_')) and hasattr(v, 'poll') and v.poll() is None]
assert not active, ('Existing background jobs must finish first', active)
jobs = []
for fps in [30, 120]:
    directory = root / f'{fps}Hz'
    directory.mkdir(exist_ok=True)
    assert not (directory / 'trace_result.json').exists()
    key = f'MMD_BACKGROUND_jiggle_timing_trace_{fps}Hz01'
    argv = [r'D:\software\blender\5.2.1\blender.exe', '--background', '--factory-startup', '--threads', '4',
            '--python', str(repo / 'scripts/trace_jiggle_timing_pipeline.py'), '--',
            '--out', str(directory), '--fps', str(fps), '--last', '391']
    log = root / f'{fps}Hz.log'
    with log.open('ab') as stream:
        process = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                   cwd=str(repo), creationflags=subprocess.CREATE_NO_WINDOW)
    bpy.app.driver_namespace[key] = process
    jobs.append(dict(fps=fps, key=key, pid=process.pid, argv=argv, log=str(log)))
record = dict(jobs=jobs, body_and_hug_preserved=True, frames=[1, 391], full_head_chains=27,
              identical_prepared_input='jiggle_naturalness_fix_20261102/B_smaller_radius',
              preroll_seconds=.5, only_experimental_variable='integration frequency, with matched physical preroll duration',
              observer='Python profiler reads plugin locals, no solver code or functions replaced',
              worker_sha256=hashlib.sha256((repo / 'scripts/trace_jiggle_timing_pipeline.py').read_bytes()).hexdigest(),
              shutdown_forbidden=True)
(root / 'launch.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps([dict(fps=j['fps'], pid=j['pid']) for j in jobs]))
