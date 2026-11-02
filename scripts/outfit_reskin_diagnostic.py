"""Save the garment immediately after rig mapping, before any surface fit."""
import argparse
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine, prepare_target
from mmd_outfit.jobs import read_json

parser = argparse.ArgumentParser()
parser.add_argument("--profile", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
profile = read_json(args.profile)
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
ie, dressing, extraction, garment = map(engine, ("import_export", "dressing", "extraction", "garment"))
ie.ensure_mmd_tools()
ie.clear_scene()
src = ie.import_pmx(profile["source"]["path"])
tgt = ie.import_pmx(profile["target"]["path"])
prepare_target(ie.model_meshes(tgt)[0], profile["target_exclude_materials"])
parts = extraction.enumerate_parts(ie.model_meshes(src))
selected = [p["id"] for p in parts if p["material"] in profile["selected_materials"]]
extracted = garment.extract_clothing(src, parts, selected, str(out / "extracted"), name="Cloth")
cloth = extracted["cloth"][0]
sa = next(o for o in src if o.type == "ARMATURE")
ta = next(o for o in tgt if o.type == "ARMATURE")
mapping = dressing.build_rig_map(sa, ta, set(extracted["summary"]["used_bones"]))
deltas = dressing.rest_deltas(sa, ta, mapping["mapping"])
deltas.update(dressing.garment_deltas(sa, mapping["garment_bones"], deltas))
dressing.add_bones(ta, dressing.garment_bone_specs(sa, mapping["garment_bones"], deltas))
bone_map = dict(mapping["mapping"])
bone_map.update({n: n for n in mapping["garment_bones"]})
dressing.reskin(cloth, deltas, bone_map)
for modifier in list(cloth.modifiers):
    if modifier.type == "ARMATURE":
        cloth.modifiers.remove(modifier)
cloth.modifiers.new("Armature", "ARMATURE").object = ta
cloth.parent = ta
cloth.matrix_parent_inverse = ta.matrix_world.inverted()
for obj in src:
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.wm.save_as_mainfile(filepath=str(out / "reskinned.blend"))
extraction.render_objects(ie.model_meshes(), out / "preview", width=600, height=800)
