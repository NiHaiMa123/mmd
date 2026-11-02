"""Render the unmodified source to distinguish design details from fit defects."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json
profile = read_json(sys.argv[sys.argv.index("--") + 1])
ie = engine("import_export")
ie.ensure_mmd_tools()
ie.clear_scene()
objects = ie.import_pmx(profile["source"]["path"])
engine("extraction").render_objects(ie.model_meshes(objects), ROOT / "outputs/v02_source_reference", width=900, height=1200)
