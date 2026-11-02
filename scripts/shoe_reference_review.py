"""Render unmodified source shoes and target bare feet, with bone landmarks."""
import argparse
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--profile", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
profile = read_json(args.profile)
out = Path(args.output)
out.mkdir(parents=True, exist_ok=True)
ie, render = engine("import_export"), engine("extraction")
ie.ensure_mmd_tools()
records = {}
for side in ("source", "target"):
    ie.clear_scene()
    objects = ie.import_pmx(profile[side]["path"])
    arm = next(obj for obj in objects if obj.type == "ARMATURE")
    bones = arm.data.bones
    records[side] = {name: {"head": list(bones[name].head_local), "tail": list(bones[name].tail_local),
                            "parent": bones[name].parent.name if bones[name].parent else None}
                     for name in ("足首.L", "足首D.L", "足先EX.L", "つま先.L", "足ＩＫ.L", "つま先ＩＫ.L") if name in bones}
    ankles = [bones[name].head_local for name in ("足首.L", "足首.R")]
    center = (ankles[0] + ankles[1]) * .5 - Vector((0, 0, .015))
    scene = bpy.context.scene
    render._setup_render(scene, 900, 900)
    render._setup_lights(scene)
    data = bpy.data.cameras.new("ShoeReviewCamera")
    data.type = "ORTHO"
    data.ortho_scale = .36
    camera = bpy.data.objects.new("ShoeReviewCamera", data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    for name, direction in (("front", (0, -1, 0)), ("oblique", (1, -1, .05)), ("side", (1, 0, 0))):
        camera.location = center + Vector(direction).normalized() * 3
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out / f"{side}_{name}.png")
        bpy.ops.render.render(write_still=True)
write_json(out / "landmarks.json", records)
