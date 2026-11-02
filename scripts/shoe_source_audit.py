"""Audit the actual shoe panels and source foot/stocking surfaces."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json
profile = read_json(sys.argv[sys.argv.index("--") + 1])
out = ROOT / "outputs/shoe_source_audit"
out.mkdir(parents=True, exist_ok=True)
ie, render = engine("import_export"), engine("extraction")
ie.clear_scene()
objects = ie.import_pmx(profile["source"]["path"])
mesh = ie.model_meshes(objects)[0]
report = {}
from collections import Counter
edge_counts = Counter(tuple(sorted((face.vertices[i], face.vertices[(i + 1) % len(face.vertices)])))
                      for face in mesh.data.polygons
                      if mesh.data.materials[face.material_index].name == "腿"
                      for i in range(len(face.vertices)))
boundary = sorted({i for edge, count in edge_counts.items() if count == 1
                   and all(mesh.data.vertices[i].co.z < .15 for i in edge) for i in edge})
write_json(out / "ankle_boundary.json", {"vertices": boundary,
    "positions": [list(mesh.data.vertices[i].co) for i in boundary]})
for material in mesh.data.materials:
    ids = {i for face in mesh.data.polygons if mesh.data.materials[face.material_index] == material
           and max(mesh.data.vertices[i].co.z for i in face.vertices) < .15 for i in face.vertices}
    if not ids:
        continue
    points = [mesh.data.vertices[i].co for i in ids]
    report[material.name] = {"vertices": len(ids),
        "min": [min(p[a] for p in points) for a in range(3)],
        "max": [max(p[a] for p in points) for a in range(3)]}
write_json(out / "materials.json", report)
print(json.dumps(report, ensure_ascii=True), flush=True)
for obj in objects:
    obj.hide_render = obj != mesh
scene = bpy.context.scene
render._setup_render(scene, 1000, 1000)
render._setup_lights(scene)
data = bpy.data.cameras.new("AuditCamera")
data.type = "ORTHO"
data.ortho_scale = .32
camera = bpy.data.objects.new("AuditCamera", data)
scene.collection.objects.link(camera)
scene.camera = camera
center = Vector((.055, -.035, .085))
for name, direction in (("inner", (-1, 0, 0)), ("inner_oblique", (-1, -1, .05))):
    camera.location = center + Vector(direction).normalized() * 3
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / f"source_{name}.png")
    bpy.ops.render.render(write_still=True)
