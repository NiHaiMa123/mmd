"""Re-extract untouched shoes and align by one similarity transform per side.

This is an isolated fitting experiment, not the legacy anisotropic foot_last.
It writes only a new output directory and never modifies input PMX files.
"""
import argparse
from collections import Counter
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))
from mmd_outfit.service import engine, prepare_target
from mmd_outfit.jobs import read_json, write_json

parser = argparse.ArgumentParser()
parser.add_argument("--profile", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--scale", type=float, default=1.1)
parser.add_argument("--forward", type=float, default=0)
parser.add_argument("--height", type=float, default=0)
parser.add_argument("--align-yaw", action="store_true")
parser.add_argument("--foot-pitch", type=float, default=0)
parser.add_argument("--heel-forward", type=float, default=0)
parser.add_argument("--foot-width", type=float, default=1)
parser.add_argument("--body-lift", type=float, default=0)
parser.add_argument("--closed-foot-mask-offset", type=float)
parser.add_argument("--collar-mask", action="store_true")
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
profile = read_json(args.profile)
out = Path(args.output).resolve()
out.mkdir(parents=True, exist_ok=True)
ie, dressing, garment, render = [engine(n) for n in ("import_export", "dressing", "garment", "extraction")]
ie.clear_scene()
src = ie.import_pmx(profile["source"]["path"])
tgt = ie.import_pmx(profile["target"]["path"])
source = ie.model_meshes(src)[0]
target = ie.model_meshes(tgt)[0]
source_arm = next(o for o in src if o.type == "ARMATURE")
target_arm = next(o for o in tgt if o.type == "ARMATURE")
prepare_target(target, [m.name for m in target.data.materials if m.name not in {"Body", "Nails"}])
if args.body_lift:
    offset = Vector((0, 0, args.body_lift))
    physics_matrices = {o: o.matrix_world.copy() for o in tgt
                        if getattr(o, "mmd_type", "NONE") in {"RIGID_BODY", "JOINT"}}
    dressing.apply_positions(target.data, [v.co + offset for v in target.data.vertices])
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    target_arm.hide_set(False)
    target_arm.select_set(True)
    bpy.context.view_layer.objects.active = target_arm
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in target_arm.data.edit_bones:
        bone.head += offset
        bone.tail += offset
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    for obj, matrix in physics_matrices.items():
        matrix.translation += offset
        obj.matrix_world = matrix
for obj in src + tgt:
    obj.hide_render = obj != target
regions = dressing.limb_regions(source)
shoe_faces = [p.index for p in source.data.polygons
              if source.data.materials[p.material_index].name in {"服", "服+jinshu"}
              and max(source.data.vertices[i].co.z for i in p.vertices) < .15]
shoes, used = garment._copy_mesh_subset(source, shoe_faces, "Original_Shoes_Similarity")
shoe_positions = [v.co.copy() for v in shoes.data.vertices]
transforms = {}
target_regions = dressing.limb_regions(target)
for side, sign in (("L", 1), ("R", -1)):
    src_anchor = source_arm.data.bones["足首." + side].head_local
    tgt_anchor = target_arm.data.bones["足首." + side].head_local
    destination = tgt_anchor + Vector((0, args.forward, args.height))
    ids = [v.index for v in shoes.data.vertices if v.co.x * sign > 0]
    source_points = [shoe_positions[i] for i in ids]
    target_points = [v.co for v, region in zip(target.data.vertices, target_regions)
                     if region == "foot_" + side and v.co.z <= tgt_anchor.z + .02]
    def horizontal_axis(points):
        ys = np.asarray([p.y for p in points])
        front = [p for p in points if p.y <= np.quantile(ys, .15)]
        back = [p for p in points if p.y >= np.quantile(ys, .85)]
        vector = sum(front, Vector()) / len(front) - sum(back, Vector()) / len(back)
        return math.atan2(vector.y, vector.x)
    yaw = horizontal_axis(target_points) - horizontal_axis(source_points) if args.align_yaw else 0
    matrix = (Matrix.Translation(destination) @ Matrix.Rotation(yaw, 4, 'Z') @
              Matrix.Scale(args.scale, 4) @ Matrix.Translation(-src_anchor))
    for i in ids:
        shoe_positions[i] = matrix @ shoe_positions[i]
    transforms[side] = {"scale": args.scale, "yaw_degrees": math.degrees(yaw),
                        "matrix": [list(row) for row in matrix], "vertices": len(ids)}
dressing.apply_positions(shoes.data, shoe_positions)

original_target = [v.co.copy() for v in target.data.vertices]
target_positions = [p.copy() for p in original_target]
def smooth01(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)

foot_edits = []
if args.foot_pitch or args.heel_forward or args.foot_width != 1:
    rotation = Matrix.Rotation(math.radians(args.foot_pitch), 3, 'X')
    for i, point in enumerate(original_target):
        side = "L" if point.x > 0 else "R"
        anchor = target_arm.data.bones["足首." + side].head_local
        # Dominant-weight labels switch abruptly around the ankle. A geometric
        # falloff treats all adjacent skin/toenail vertices continuously.
        influence = 1 - smooth01((point.z - anchor.z) / .07)
        if not influence:
            continue
        posed = anchor + rotation @ (point - anchor)
        posed.x = anchor.x + (posed.x - anchor.x) * args.foot_width
        heel = smooth01((point.y - (anchor.y - .005)) / .035)
        posed.y -= args.heel_forward * heel
        target_positions[i] = point.lerp(posed, influence)
        foot_edits.append((target_positions[i] - point).length)
    dressing.apply_positions(target.data, target_positions)

foot_backup = None
foot_mask = {"enabled": False, "removed_faces": 0}
collar_fields = {}
if args.collar_mask:
    # Weld UV seams by position before identifying the genuine lower boundary.
    def key(point):
        return tuple(round(float(c), 6) for c in point)
    edge_counts = Counter(tuple(sorted((key(source.data.vertices[f.vertices[j]].co),
        key(source.data.vertices[f.vertices[(j + 1) % len(f.vertices)]].co))))
        for f in source.data.polygons if source.data.materials[f.material_index].name == "腿"
        for j in range(len(f.vertices)))
    boundary = {p for edge, count in edge_counts.items() if count == 1
                and all(p[2] < .15 for p in edge) for p in edge}
    for side, sign in (("L", 1), ("R", -1)):
        matrix = Matrix(transforms[side]["matrix"])
        points = np.asarray([matrix @ Vector(p) for p in boundary if p[0] * sign > 0])
        assert len(points) >= 6, (side, points)
        basis = np.column_stack((points[:, 0], points[:, 1], np.ones(len(points))))
        plane = np.linalg.lstsq(basis, points[:, 2], rcond=None)[0]
        residual = points[:, 2] - basis @ plane
        collar_fields[side] = points, plane, residual

def cut_height(point):
    side = "L" if point.x > 0 else "R"
    if not args.collar_mask:
        return target_arm.data.bones["足首." + side].head_local.z + args.closed_foot_mask_offset
    points, plane, residual = collar_fields[side]
    distance = np.sum((points[:, :2] - (point.x, point.y)) ** 2, axis=1)
    weights = 1 / (distance + .005 ** 2) ** 2
    return float(np.dot((point.x, point.y, 1), plane) + np.dot(weights, residual) / weights.sum() - .006)

if args.closed_foot_mask_offset is not None or args.collar_mask:
    removed = [f.index for f in target.data.polygons
               if target.data.materials[f.material_index].name in {"Body", "Nails"}
               and all(target.data.vertices[i].co.z < cut_height(target.data.vertices[i].co)
                       for i in f.vertices)]
    foot_backup, _ = garment._copy_mesh_subset(target, removed, "Hidden_Foot_Backup")
    foot_backup.hide_render = True
    removed_set = set(removed)
    retained, _ = garment._copy_mesh_subset(target,
        [f.index for f in target.data.polygons if f.index not in removed_set], "RetainedBody")
    names = [g.name for g in retained.vertex_groups]
    target.vertex_groups.clear()
    target.data = retained.data
    for name in names:
        target.vertex_groups.new(name=name)
    bpy.data.objects.remove(retained, do_unlink=True)
    target_regions = dressing.limb_regions(target)
    foot_mask = {"enabled": True, "removed_faces": len(removed), "offset": args.closed_foot_mask_offset,
                 "method": "source_collar_field" if args.collar_mask else "horizontal_cut",
                 "boundary_controls": {s: p[0].tolist() for s, p in collar_fields.items()},
                 "backup_object": foot_backup.name, "scope": "closed shoes only; original input unchanged"}

def bbox(points):
    return {"min": [min(p[a] for p in points) for a in range(3)],
            "max": [max(p[a] for p in points) for a in range(3)]}

report = {"method": "original_shoe_similarity_probe", "transforms": transforms,
          "shoe_faces": len(shoe_faces), "shoe_vertices": len(used), "source_vertex_ids": used}
report["foot_shape"] = {"pitch_degrees": args.foot_pitch, "heel_forward": args.heel_forward,
                         "width_scale": args.foot_width,
                         "global_model_lift": args.body_lift,
                         "edited_vertices": len(foot_edits), "max_displacement": max(foot_edits, default=0),
                         "scope": "local foot shape and global model height experiment; no weight transfer or VMD acceptance yet"}
report["foot_mask"] = foot_mask
for side, sign in (("L", 1), ("R", -1)):
    ids = [v.index for v in shoes.data.vertices if v.co.x * sign > 0]
    source_points = [source.data.vertices[used[i]].co for i in ids]
    points = [shoes.data.vertices[i].co for i in ids]
    feet = [v.co for v, region in zip(target.data.vertices, target_regions)
            if region == "foot_" + side and v.co.z < target_arm.data.bones["足首." + side].head_local.z + .02]
    ratios = []
    ids_set = set(ids)
    for edge in shoes.data.edges:
        a, b = edge.vertices
        if a in ids_set and b in ids_set:
            old = (source.data.vertices[used[a]].co - source.data.vertices[used[b]].co).length
            if old > 1e-7:
                ratios.append((shoes.data.vertices[a].co - shoes.data.vertices[b].co).length / old)
    report[side] = {"shoe_bbox": bbox(points), "source_bbox": bbox(source_points),
                    "foot_bbox": bbox(feet), "edge_scale_min": min(ratios), "edge_scale_max": max(ratios)}
write_json(out / "alignment.json", report)

scene = bpy.context.scene
render._setup_render(scene, 1000, 1000)
render._setup_lights(scene)
data = bpy.data.cameras.new("ShoeFitCamera")
data.type = "ORTHO"
data.ortho_scale = .42
camera = bpy.data.objects.new("ShoeFitCamera", data)
scene.collection.objects.link(camera)
scene.camera = camera
ankles = [target_arm.data.bones["足首." + s].head_local for s in ("L", "R")]
center = (ankles[0] + ankles[1]) * .5 - Vector((0, .04, .015))
for name, direction in (("front", (0, -1, .05)), ("oblique", (1, -1, .05)), ("side", (1, 0, 0)),
                        ("back", (0, 1, 0))):
    camera.location = center + Vector(direction).normalized() * 3
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / f"fit_{name}.png")
    bpy.ops.render.render(write_still=True)
shoes.hide_render = True
if foot_backup:
    foot_backup.hide_render = False
for name, direction in (("side", (1, 0, 0)), ("oblique", (1, -1, .05))):
    camera.location = center + Vector(direction).normalized() * 3
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / ("foot_shape_" + name + ".png"))
    bpy.ops.render.render(write_still=True)
shoes.hide_render = False
if foot_backup:
    foot_backup.hide_render = True
bpy.ops.wm.save_as_mainfile(filepath=str(out / "fit.blend"))
print("SHOE_PROBE", {s: report[s] for s in ("L", "R")}, flush=True)
