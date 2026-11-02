"""Normal full-character image sequences, using existing bakes only."""
import json
import runpy
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
root = repo.parent / 'work/headswap_xl_codex/jiggle_timing_trace_20261102'
for fps in [30, 120]:
    folder = root / f'{fps}Hz'
    source = json.loads((folder / 'bake_report.json').read_text(encoding='utf-8'))['blend']
    sys.argv = [str(repo / 'scripts/render_baked_hair_review.py'), '--', '--source', source,
                '--out', str(folder / 'continuous_review'), '--start-seconds', '11.25',
                '--duration', '1.5', '--fps', '24', '--samples', '24']
    runpy.run_path(str(repo / 'scripts/render_baked_hair_review.py'), run_name='__main__')
