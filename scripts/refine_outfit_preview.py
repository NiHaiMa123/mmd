"""Preview current regional rules on an existing coarse, unrefined Blend."""
import argparse
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.surface_fit import apply_rules
from mmd_outfit.jobs import read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    for key in ("blend", "profile", "out"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--subdivide-only", action="store_true")
    parser.add_argument("--all-layers", action="store_true")
    parser.add_argument("--method", default="radial_order")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    directory = Path(args.out)
    directory.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    ie = engine("import_export")
    meshes = ie.model_meshes()
    cloth = next(obj for obj in meshes if obj.get("mmd_garment"))
    body = next(obj for obj in meshes if obj is not cloth)
    arm = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    profile = read_json(args.profile)
    rules = profile["clearance_rules"]
    for rule in rules:
        rule["method"] = args.method
    body_bones = set(profile["common_bones"])
    if args.all_layers:
        body_bones.update(group.name for group in cloth.vertex_groups)
    report = apply_rules(cloth, body, arm, body_bones, rules,
                         (lambda mesh, positions: None) if args.subdivide_only else engine("dressing").apply_positions,
                         engine("dressing").subdivide_triangles)
    write_json(directory / "refinement.json", report)
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "refined.blend"))
    engine("extraction").render_objects(meshes, directory / "preview", width=600, height=800)
    print(report, flush=True)


if __name__ == "__main__":
    main()
