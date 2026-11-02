"""Preview conservative whole-face collar trimming on a completed Blend."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json
from mmd_outfit.preserved_shoe import CollarField, replace_mesh
job = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
rim_scale = float(sys.argv[-1]) if sys.argv[-1] != str(job) else 1
result = read_json(job / "result.json")
shoe = read_json(job / "adaptation_report.json")["shoes"]
profile = read_json(job / "profile_snapshot.json")
bpy.ops.wm.open_mainfile(filepath=result["blend"])
ie, render = engine("import_export"), engine("extraction")
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
fields = {s: CollarField(shoe["sides"][s]["boundary_controls"], profile["shoe_fit"]["mask_depth"]) for s in ("L", "R")}
report = {}
for obj in ie.model_meshes(list(bpy.data.objects)):
    remove = []
    if rim_scale != 1:
        skin_ids = {i for f in obj.data.polygons if obj.data.materials[f.material_index].name in {"Body", "Nails", "腿"} for i in f.vertices}
        updated = [v.co.copy() for v in obj.data.vertices]
        for i in skin_ids:
            point = updated[i]
            side = 'L' if point.x > 0 else 'R'
            ankle = arm.data.bones['足首.' + side].head_local
            weight = max(0, min(1, (ankle.z + .045 - point.z) / .065))
            factor = 1 - (1-rim_scale) * (weight * weight * (3 - 2*weight))
            if abs(point.x-ankle.x) < .12 and abs(point.y-ankle.y) < .25:
                point.x = ankle.x + (point.x-ankle.x)*factor
                point.y = ankle.y + (point.y-ankle.y)*factor
        engine('dressing').apply_positions(obj.data, updated)
        continue
    for face in obj.data.polygons:
        if obj.data.materials[face.material_index].name not in {"Body", "Nails", "腿"}:
            continue
        points = [obj.data.vertices[i].co for i in face.vertices]
        side = "L" if sum(p.x for p in points) > 0 else "R"
        ankle = arm.data.bones["足首." + side].head_local
        if all(p.z < ankle.z + .06 and abs(p.x - ankle.x) < .12 and abs(p.y - ankle.y) < .25 for p in points) and any(p.z < fields[side].height(p) for p in points):
            remove.append(face.index)
    if remove:
        retained, _ = engine("garment")._copy_mesh_subset(obj, [f.index for f in obj.data.polygons if f.index not in set(remove)], "trimmed")
        replace_mesh(obj, retained)
    report[obj.name] = len(remove)
out = job / ("collar_rim_" + str(rim_scale) if rim_scale != 1 else "collar_trim_preview")
out.mkdir(exist_ok=True)
render._setup_render(bpy.context.scene, 1000, 1000)
render._setup_lights(bpy.context.scene)
data = bpy.data.cameras.new("CollarPreview")
data.type = 'ORTHO'
data.ortho_scale = .42
camera = bpy.data.objects.new("CollarPreview", data)
bpy.context.scene.collection.objects.link(camera)
bpy.context.scene.camera = camera
center = (arm.data.bones["足首.L"].head_local + arm.data.bones["足首.R"].head_local) * .5 - Vector((0, .03, .015))
for name, direction in (("front", (0, -1, .03)), ("back", (0, 1, 0)), ("side", (1, 0, 0)), ("oblique", (1, -1, .03))):
    camera.location = center + Vector(direction).normalized() * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.render.filepath = str(out / (name + '.png'))
    bpy.ops.render.render(write_still=True)
write_json(out / 'report.json', report)
print('COLLAR_TRIM', report, flush=True)
