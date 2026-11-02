"""Repository convenience entry; the portable benchmark ships in the add-on."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1]/'addon/animation_contact_tools/curve_benchmark.py'),run_name='__main__')
