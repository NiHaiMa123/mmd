"""Preview target-derived glove/sock patches on an unrefined rig-mapped model."""
import argparse
from pathlib import Path
import sys
import bpy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.skin_patch import rebuild
from mmd_outfit.foot_last import fit as fit_shoes
from mmd_outfit.jobs import write_json
parser = argparse.ArgumentParser()
parser.add_argument("--blend", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--foot-only", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=args.blend)
ie, garment = engine("import_export"), engine("garment")
cloth = next(o for o in ie.model_meshes() if o.get("mmd_garment"))
body = next(o for o in ie.model_meshes() if o is not cloth)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
dressing = engine("dressing")
report = [fit_shoes(cloth, body, arm, dressing.apply_positions, dressing.limb_regions, margin=.010)]
for region, material in (() if args.foot_only else (("hands", "服"), ("legs", "腿"))):
    report.append(rebuild(cloth, body, arm, {"region": region, "material": material,
        "skin_material": "Body", "margin": .0015,
        "include_skin_materials": ["Nails"] if region == "hands" else [],
        "lower_offset": -.035}, garment._copy_mesh_subset))
write_json(out / "patches.json", report)
bpy.ops.wm.save_as_mainfile(filepath=str(out / "patches.blend"))
engine("extraction").render_objects(ie.model_meshes(), out / "preview", width=600, height=800)
print(report, flush=True)
