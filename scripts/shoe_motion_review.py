"""Verify preserved shoes after PMX roundtrip and render actual VMD foot poses.

Blender --python this.py -- --job <completed fit directory>
No dynamics are simulated; shape checks do not replace visual collar review.
"""
import argparse
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--job", required=True)
parser.add_argument('--extra-frame',type=int,action='append',default=[])
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
job = Path(args.job).resolve()
request, result = read_json(job / "request.json"), read_json(job / "result.json")
profile = read_json(job / "profile_snapshot.json")
shoe = read_json(job / "adaptation_report.json")["shoes"]
out = job / "shoe_review"
out.mkdir(exist_ok=True)
ie, render = engine("import_export"), engine("extraction")

def tree(points):
    value = KDTree(len(points))
    for i, point in enumerate(points):
        value.insert(point, i)
    value.balance()
    return value

ie.clear_scene()
source = ie.import_pmx(profile["source"]["path"])
source_mesh = ie.model_meshes(source)[0]
expected = []
for i in shoe["original_source_vertex_ids"]:
    point = source_mesh.data.vertices[i].co
    matrix = Matrix(shoe["sides"]["L" if point.x > 0 else "R"]["matrix"])
    expected.append(matrix @ point)
ie.clear_scene()
bpy.ops.wm.open_mainfile(filepath=result["blend"])
backup = bpy.data.objects.get(shoe["foot_backup_object"])
assert backup is not None and backup.hide_render and backup.parent is None
backup_report = {"name": backup.name, "faces": len(backup.data.polygons),
                 "hidden": backup.hide_render, "outside_export_armature": backup.parent is None,
                 "shape_keys": len(backup.data.shape_keys.key_blocks) if backup.data.shape_keys else 0}
assert backup_report["faces"] == shoe["backup_skin_faces"]
ie.clear_scene()
objects = ie.import_pmx(result["pmx"])
mesh = ie.model_meshes(objects)[0]
armature = next(o for o in objects if o.type == 'ARMATURE')
assert not any(o.name.startswith("ClosedShoe_FootBackup") for o in objects)
expected_tree = tree(expected)
matches = {v.index for v in mesh.data.vertices if expected_tree.find(v.co)[2] < 1e-5}
faces = [f for f in mesh.data.polygons
         if mesh.data.materials[f.material_index].name in profile["shoe_fit"]["materials"]
         and all(i in matches for i in f.vertices)]
ids = sorted({i for f in faces for i in f.vertices})
points = [mesh.data.vertices[i].co.copy() for i in ids]
assert len(faces) == shoe["source_faces"], (len(faces), shoe["source_faces"])
expected_tree, actual_tree = tree(expected), tree(points)
rest_error = max(max(expected_tree.find(p)[2] for p in points),
                 max(actual_tree.find(p)[2] for p in expected))
assert rest_error < 1e-5, rest_error
side_ids = {}
for side, sign in (("L", 1), ("R", -1)):
    side_ids[side] = [i for i in ids if mesh.data.vertices[i].co.x * sign > 0]
    for i in side_ids[side]:
        groups = [(mesh.vertex_groups[g.group].name, g.weight) for g in mesh.data.vertices[i].groups
                  if not mesh.vertex_groups[g.group].name.startswith("mmd_") and g.weight > 1e-6]
        assert len(groups) == 1 and groups[0][0] == "足首D." + side and abs(groups[0][1] - 1) < 1e-6, groups
rest = {side: np.asarray([tuple(mesh.data.vertices[i].co) for i in values]) for side, values in side_ids.items()}

scene = bpy.context.scene
render._setup_render(scene, 1000, 1000)
render._setup_lights(scene)
data = bpy.data.cameras.new("ShoeReviewCamera")
data.type = 'ORTHO'
camera = bpy.data.objects.new("ShoeReviewCamera", data)
scene.collection.objects.link(camera)
scene.camera = camera
images = []

def shot(name, direction):
    anchors = [armature.matrix_world @ armature.pose.bones["足首D." + s].head for s in ("L", "R")]
    center = (anchors[0] + anchors[1]) * .5 - Vector((0, .03, .015))
    data.ortho_scale = max(.42, (anchors[0] - anchors[1]).length * 1.55 + .18)
    camera.location = center + Vector(direction).normalized() * 3
    camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(out / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    images.append(scene.render.filepath)

for name, direction in (("rest_front", (0, -1, .03)), ("rest_oblique", (1, -1, .03)),
                        ("rest_side", (1, 0, 0)), ("rest_back", (0, 1, 0))):
    shot(name, direction)
for obj in bpy.context.selected_objects:
    obj.select_set(False)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature
motion_path=result.get('effective_motion') or request['motion']
bpy.ops.mmd_tools.import_vmd(filepath=motion_path, scale=.08, rename_bones=True, log_level='ERROR')
frames = list(range(scene.frame_start, scene.frame_end + 1, 15))[:24]
frames = sorted(set(frames + [1, 121, 256]+args.extra_frame))
checks = []
for frame in frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    evaluated = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    current = evaluated.to_mesh()
    item = {"frame": frame, "sides": {}}
    for side, values in side_ids.items():
        posed = np.asarray([tuple(current.vertices[i].co) for i in values])
        original = rest[side]
        a, b = original - original.mean(axis=0), posed - posed.mean(axis=0)
        u, _, vt = np.linalg.svd(a.T @ b)
        correction = np.eye(3)
        correction[2, 2] = np.linalg.det(u @ vt)
        rotation = u @ correction @ vt
        residual = float(np.max(np.linalg.norm(a @ rotation - b, axis=1)))
        assert residual < 3e-5, (frame, side, residual)
        item["sides"][side] = {"max_rigid_fit_residual_m": residual,
                                "lowest_vertex_z_m": float(posed[:, 2].min())}
    evaluated.to_mesh_clear()
    checks.append(item)
    if frame in {1, 121, 256,*args.extra_frame}:
        shot(f"motion_{frame}_oblique", (1, -1, .03))
        shot(f"motion_{frame}_side", (1, 0, 0))
report = {"backup": backup_report, "shoe_vertices_after_export": len(ids), "shoe_faces_after_export": len(faces),
          'motion':motion_path,
          "rest_hausdorff_error_m": rest_error, "single_ankle_weights": True, "frames": checks,
          "images": images, "physics": False, "scope": "rigid shape and PMX/VMD binding; visual clipping and floor contact require review"}
write_json(out / "report.json", report)
print("SHOE_REVIEW_OK", rest_error, max(c["sides"][s]["max_rigid_fit_residual_m"] for c in checks for s in ("L", "R")), flush=True)
