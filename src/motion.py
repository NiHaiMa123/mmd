"""Motion test set and clipping detection (runs inside Blender).

P2-01  a small set of high risk poses covering the categories the plan
        lists - arms up, arms out, arms crossed, one leg up, legs apart,
        waist bend, hip turn, whole body turn.
P2-02  the metric is the number of body/cloth triangle overlaps.  In the
        rest pose the garment sits outside the body, so the count is zero;
        a pose that pushes the body through the clothes spikes it.

The poses are applied to the pose bones, so the rig really moves - the
clothes are deformed by the same armature the body uses.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# name, category, bone -> euler degrees, expectation (bone, axis, relation, value)
POSES: list[dict[str, Any]] = [
    {
        "name": "arms_up",
        "category": "双臂上举",
        "bones": {"腕.L": (-140.0, 0.0, 0.0), "腕.R": (-140.0, 0.0, 0.0)},
        "expect": {"bone": "手首.L", "axis": "z", "op": ">", "value": 1.30},
        "watch": "腋下、上衣下摆、肩缝",
    },
    {
        "name": "arms_out",
        "category": "双臂平举",
        "bones": {"腕.L": (-60.0, 0.0, -60.0), "腕.R": (-60.0, 0.0, 60.0)},
        "expect": {"bone": "手首.L", "axis": "x", "op": ">", "value": 0.32},
        "watch": "袖口、肩胸、背部",
    },
    {
        "name": "arms_cross",
        "category": "手臂交叉屈肘",
        "bones": {"腕.L": (-80.0, 0.0, 35.0), "腕.R": (-80.0, 0.0, -35.0),
                  "ひじ.L": (0.0, 0.0, 80.0), "ひじ.R": (0.0, 0.0, -80.0)},
        "candidates": [
            {"腕.L": (-80.0, 0.0, 35.0), "腕.R": (-80.0, 0.0, -35.0),
             "ひじ.L": (0.0, 0.0, 80.0), "ひじ.R": (0.0, 0.0, -80.0)},
            {"腕.L": (-80.0, 0.0, 70.0), "腕.R": (-80.0, 0.0, -70.0),
             "ひじ.L": (0.0, 0.0, 80.0), "ひじ.R": (0.0, 0.0, -80.0)},
            {"腕.L": (-60.0, 0.0, 100.0), "腕.R": (-60.0, 0.0, -100.0),
             "ひじ.L": (0.0, 0.0, 90.0), "ひじ.R": (0.0, 0.0, -90.0)},
        ],
        "expect": {"bone": "手首.L", "axis": "x", "op": "<", "value": 0.10},
        "watch": "袖子扭曲、胳膊穿衣",
    },
    {
        "name": "leg_up",
        "category": "单腿抬高及屈膝",
        "bones": {"足.L": (35.0, 0.0, 0.0), "ひざ.L": (0.0, 0.0, -60.0)},
        "candidates": [
            {"足.L": (35.0, 0.0, 0.0), "ひざ.L": (0.0, 0.0, -60.0)},
            {"足.L": (-35.0, 0.0, 0.0), "ひざ.L": (0.0, 0.0, -60.0)},
            {"足.L": (0.0, 35.0, 0.0), "ひざ.L": (0.0, 0.0, -60.0)},
            {"足.L": (0.0, -35.0, 0.0), "ひざ.L": (0.0, 0.0, -60.0)},
        ],
        "expect": {"bone": "足首.L", "axis": "z", "op": ">", "value": 0.32},
        "watch": "裤腿、裙摆、胯部",
    },
    {
        "name": "legs_split",
        "category": "双腿分开/深蹲",
        "bones": {"足.L": (0.0, 0.0, 22.0), "足.R": (0.0, 0.0, -22.0)},
        "candidates": [
            {"足.L": (0.0, 0.0, 22.0), "足.R": (0.0, 0.0, -22.0)},
            {"足.L": (0.0, 22.0, 0.0), "足.R": (0.0, -22.0, 0.0)},
            {"足.L": (0.0, -22.0, 0.0), "足.R": (0.0, 22.0, 0.0)},
            {"足.L": (0.0, 0.0, 40.0), "足.R": (0.0, 0.0, -40.0)},
        ],
        "expect": {"bone": "足首.L", "axis": "x", "op": ">", "value": 0.13},
        "watch": "裙摆或裤裆变形",
    },
    {
        "name": "waist_bend",
        "category": "腰部前倾",
        "bones": {"上半身2": (28.0, 0.0, 0.0)},
        "expect": {"bone": "頭", "axis": "z", "op": "<", "value": 1.40},
        "watch": "腰、背、衣服下沿",
    },
    {
        "name": "hip_turn",
        "category": "坐姿或大幅屈髋",
        "bones": {"下半身": (0.0, 0.0, 25.0), "上半身2": (-18.0, 0.0, 0.0)},
        "expect": {"bone": "頭", "axis": "z", "op": "<", "value": 1.42},
        "watch": "腰臀、裙摆、腿",
    },
    {
        "name": "body_turn",
        "category": "转身",
        "bones": {"センター": (0.0, 0.0, 35.0)},
        "expect": {"bone": "頭", "axis": "x", "op": ">", "value": 0.10},
        "watch": "宽松部件及裙摆",
    },
]


def resolve_pose(armature: bpy.types.Object, pose: dict[str, Any],
                 state: list[tuple] | None = None) -> tuple[dict, bool]:
    """Pick the candidate rotation that actually produces the intended pose.

    Bone local axes differ between rigs, so the direction that raises an arm
    is not universal - the candidates are tried and the one that satisfies the
    expectation wins.
    """
    candidates = pose.get("candidates") or [pose["bones"]]
    for cand in candidates:
        reset_pose(armature, state)
        apply_pose(armature, {"bones": cand})
        if check_expectation(armature, pose):
            return cand, True
    reset_pose(armature, state)
    apply_pose(armature, {"bones": candidates[0]})
    return candidates[0], check_expectation(armature, pose)


def _pose_bone(armature: bpy.types.Object, name: str):
    return armature.pose.bones.get(name)


def capture_pose(armature: bpy.types.Object) -> list[tuple]:
    """Remember the pose so it can be restored exactly.

    Switching a pose bone to XYZ silently drops a quaternion rotation, and
    MMD models can carry a non trivial initial pose - resetting to zero
    would move the body and change how the toon shader shades it.
    """
    state = []
    for pb in armature.pose.bones:
        state.append((pb, pb.rotation_mode, pb.rotation_euler.copy(),
                      pb.rotation_quaternion.copy(), pb.location.copy(),
                      pb.scale.copy()))
    return state


def restore_pose(armature: bpy.types.Object, state: list[tuple]) -> None:
    for pb, mode, euler, quat, loc, scale in state:
        pb.rotation_mode = mode
        if mode == 'QUATERNION':
            pb.rotation_quaternion = quat
        else:
            pb.rotation_euler = euler
        pb.location = loc
        pb.scale = scale
    bpy.context.view_layer.update()


def apply_pose(armature: bpy.types.Object, pose: dict[str, Any]) -> list[str]:
    """Set the bone rotations of one pose; returns the bones actually used."""
    used = []
    for name, rot in pose["bones"].items():
        pb = _pose_bone(armature, name)
        if pb is None:
            continue
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = tuple(math.radians(a) for a in rot)
        used.append(name)
    bpy.context.view_layer.update()
    return used


def reset_pose(armature: bpy.types.Object,
               state: list[tuple] | None = None) -> None:
    if state is not None:
        restore_pose(armature, state)
        return
    for pb in armature.pose.bones:
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def check_expectation(armature: bpy.types.Object, pose: dict[str, Any]) -> bool:
    exp = pose.get("expect")
    if not exp:
        return True
    pb = _pose_bone(armature, exp["bone"])
    if pb is None:
        return False
    value = pb.head[{"x": 0, "y": 1, "z": 2}[exp["axis"]]]
    target = exp["value"]
    if exp["op"] == ">":
        return value > target
    return value < target


def _evaluated(obj: bpy.types.Object):
    """Evaluate a mesh and return (mesh, owner).

    The owner has to be the *evaluated* object: calling to_mesh_clear() on
    the original one would free the mesh the depsgraph is using and the
    body would be evaluated from garbage.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh(depsgraph=depsgraph, preserve_all_data_layers=True)
    return me, ev


def _bvh_from(me, face_indices: list[int]) -> BVHTree:
    verts = [v.co.copy() for v in me.vertices]
    polys = [list(me.polygons[i].vertices) for i in face_indices
             if i < len(me.polygons)]
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def overlap_count(body_bvh: BVHTree, cloth_bvh: BVHTree) -> int:
    """How many body/cloth triangle bounding boxes overlap (contact proxy)."""
    return len(body_bvh.overlap(cloth_bvh))


def _poking_count(body_bvh: BVHTree, cloth_bvh: BVHTree, body_me,
                  bfaces: list[int], stride: int = 4,
                  max_dist: float = 0.03) -> tuple[int, int]:
    """How many body points came out through the clothes.

    A parity test does not work here: the body has holes where the mask
    removed the covered faces, so "inside" is not well defined.  The local
    test is: the nearest cloth surface has to face the same way as the body
    normal - that only happens when the body is on the outside of the cloth.
    """
    verts = set()
    for fi in bfaces:
        if fi < len(body_me.polygons):
            verts.update(body_me.polygons[fi].vertices)
    poking = 0
    checked = 0
    for i in sorted(verts)[::stride]:
        v = body_me.vertices[i]
        loc, nrm, _idx, dist = cloth_bvh.find_nearest(v.co)
        if loc is None:
            continue
        checked += 1
        if dist > max_dist:
            continue
        if nrm.dot(v.normal) > 0.3:
            poking += 1
    return poking, checked


def _pierce_count(body_bvh: BVHTree, cloth_bvh: BVHTree, body_me,
                  bfaces: list[int], rest_sign: dict[int, float],
                  stride: int = 2, max_dist: float = 0.006
                  ) -> tuple[int, int, list[int]]:
    """How many body points came out through the clothes.

    A parity test does not work: the clothes are single sided shells, so
    "inside" is not defined, and the body has holes where the mask removed
    the covered faces.

    The local test does work: in the rest pose the clothes are always
    outside the body, so the vector from a body point to the nearest cloth
    point points *outwards* along the body normal.  When the body pierces
    the cloth that vector flips - the cloth is suddenly on the inside.

    The distance check matters as much as the sign: a sleeve that simply
    swings away from a raised arm also flips the sign, but then the cloth
    is far away and nothing was pierced.
    """
    verts = set()
    for fi in bfaces:
        if fi < len(body_me.polygons):
            verts.update(body_me.polygons[fi].vertices)
    pierced = 0
    checked = 0
    hit_verts = []
    for i in sorted(verts)[::stride]:
        v = body_me.vertices[i]
        loc, _nrm, _idx, dist = cloth_bvh.find_nearest(v.co)
        if loc is None:
            continue
        checked += 1
        if dist > max_dist:
            continue
        side = (loc - v.co).dot(v.normal)
        if rest_sign.get(i, 1.0) > 0.001 and side < -0.001:
            pierced += 1
            hit_verts.append(i)
    return pierced, checked, hit_verts


def rest_side_signs(body_bvh: BVHTree, cloth_bvh: BVHTree, body_me,
                    bfaces: list[int]) -> dict[int, float]:
    """Reference: in the rest pose the cloth is outside the body."""
    verts = set()
    for fi in bfaces:
        if fi < len(body_me.polygons):
            verts.update(body_me.polygons[fi].vertices)
    out = {}
    for i in verts:
        v = body_me.vertices[i]
        loc, _nrm, _idx, _dist = cloth_bvh.find_nearest(v.co)
        if loc is None:
            continue
        out[i] = (loc - v.co).dot(v.normal)
    return out


def _inside_count(body_bvh: BVHTree, cloth_me, gfaces: list[int],
                  stride: int = 4) -> tuple[int, int]:
    """How many cloth vertices ended up inside the body.

    This is the real clipping signal: in the rest pose the garment is
    outside the body, so the count is zero, and a pose that pushes the body
    through the clothes makes it jump.
    """
    from . import qa

    verts = set()
    for fi in gfaces:
        if fi < len(cloth_me.polygons):
            verts.update(cloth_me.polygons[fi].vertices)
    total = 0
    checked = 0
    for i in sorted(verts)[::stride]:
        co = cloth_me.vertices[i].co
        if qa._inside(body_bvh, co):
            total += 1
        checked += 1
    return total, checked


def run_pose_suite(objects: list[bpy.types.Object],
                   garment_materials: list[str] | None = None,
                   out_dir: str | None = None,
                   render: bool = True) -> dict[str, Any]:
    """Apply every pose, measure the clipping and optionally screenshot.

    The clipping metric is the number of garment vertices that ended up
    inside the body.  That only works while the body is still closed, so
    this has to run *before* the body mask is applied.
    """
    from . import extraction, qa

    split = qa.split_faces(objects, garment_materials)
    gmesh = split["garment_mesh"]
    bmesh_obj = split["body_mesh"]
    gfaces = split["garment_faces"]
    bfaces = split["skin_faces"]
    if gmesh is None or bmesh_obj is None or not gfaces or not bfaces:
        return {"skipped": "model has no garment/skin face split"}

    arm = next((o for o in objects if o.type == 'ARMATURE'), None)
    if arm is None:
        return {"skipped": "no armature"}

    # the rigid body proxies are real meshes in the scene - hide them
    hidden = [o for o in objects if o.type == 'MESH' and o is not gmesh
              and o is not bmesh_obj]
    for o in hidden:
        o.hide_render = True

    out = Path(out_dir) if out_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)

    def measure(pose):
        """Clipping of one pose: body points that pierced the clothes."""
        bpy.context.view_layer.update()
        bme, bev = _evaluated(bmesh_obj)
        # a re-imported PMX keeps body and clothes in one mesh - evaluating
        # it twice would invalidate the first copy
        if gmesh is bmesh_obj:
            gme, gev = bme, bev
        else:
            gme, gev = _evaluated(gmesh)
        body_bvh = _bvh_from(bme, bfaces)
        cloth_bvh = _bvh_from(gme, gfaces)
        pierced, checked, hits = _pierce_count(body_bvh, cloth_bvh, bme,
                                               bfaces, rest_sign)
        contacts = overlap_count(body_bvh, cloth_bvh)
        bev.to_mesh_clear()
        if gev is not bev:
            gev.to_mesh_clear()
        return pierced, checked, contacts, hits

    results = []
    state = capture_pose(arm)
    try:
        reset_pose(arm, state)
        bpy.context.view_layer.update()
        bme, bev = _evaluated(bmesh_obj)
        if gmesh is bmesh_obj:
            gme, gev = bme, bev
        else:
            gme, gev = _evaluated(gmesh)
        rest_sign = rest_side_signs(_bvh_from(bme, bfaces),
                                    _bvh_from(gme, gfaces), bme, bfaces)
        bev.to_mesh_clear()
        if gev is not bev:
            gev.to_mesh_clear()

        rest_pierce, rest_checked, rest_contacts, _ = measure(None)

        for pose in POSES:
            bones, ok = resolve_pose(arm, pose, state)
            pierced, checked, contacts, hits = measure(pose)
            images = []
            if render and out:
                images = extraction.render_objects(
                    [bmesh_obj, gmesh], out, prefix=f"pose_{pose['name']}",
                    width=420, height=560)
            results.append({
                "pose": pose["name"],
                "category": pose["category"],
                "watch": pose["watch"],
                "bones_used": sorted(bones),
                "rotations": bones,
                "contacts": contacts,
                "pierced": pierced,
                "sampled": checked,
                "delta_pierced": pierced - rest_pierce,
                "expectation_met": ok,
                "images": images,
            })
        reset_pose(arm, state)
    finally:
        reset_pose(arm, state)
        for o in hidden:
            o.hide_render = False

    results.sort(key=lambda r: -r["pierced"])
    report = {
        "rest_contacts": rest_contacts,
        "rest_pierced": rest_pierce,
        "poses": results,
        "worst": results[0] if results else None,
    }
    if out:
        (out / "motion_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["report_file"] = str(out / "motion_report.json")
    return report


def poking_body_faces(objects: list[bpy.types.Object], pose: dict[str, Any],
                      garment_materials: list[str] | None = None,
                      max_ratio: float = 0.05) -> list[int]:
    """Body faces that came out through the clothes in one pose.

    Uses the same sign-flip test as the metric, so the repair targets exactly
    the places the detection complained about.  The ratio cap keeps a bad
    pose from gutting the whole body.
    """
    from . import qa

    split = qa.split_faces(objects, garment_materials)
    gmesh = split["garment_mesh"]
    bmesh_obj = split["body_mesh"]
    if gmesh is None or bmesh_obj is None:
        return []
    arm = next((o for o in objects if o.type == 'ARMATURE'), None)
    if arm is None:
        return []

    state = capture_pose(arm)
    reset_pose(arm, state)
    bpy.context.view_layer.update()
    bme, bev = _evaluated(bmesh_obj)
    if gmesh is bmesh_obj:
        gme, gev = bme, bev
    else:
        gme, gev = _evaluated(gmesh)
    rest_sign = rest_side_signs(_bvh_from(bme, split["skin_faces"]),
                                _bvh_from(gme, split["garment_faces"]),
                                bme, split["skin_faces"])
    bev.to_mesh_clear()
    if gev is not bev:
        gev.to_mesh_clear()

    resolve_pose(arm, pose, state)
    bpy.context.view_layer.update()
    bme, bev = _evaluated(bmesh_obj)
    if gmesh is bmesh_obj:
        gme, gev = bme, bev
    else:
        gme, gev = _evaluated(gmesh)
    _pierced, _checked, hits = _pierce_count(
        _bvh_from(bme, split["skin_faces"]),
        _bvh_from(gme, split["garment_faces"]), bme, split["skin_faces"],
        rest_sign, stride=1)
    hit_set = set(hits)
    doomed = []
    for fi in split["skin_faces"]:
        if any(v in hit_set for v in bme.polygons[fi].vertices):
            doomed.append(fi)
    bev.to_mesh_clear()
    if gev is not bev:
        gev.to_mesh_clear()
    reset_pose(arm, state)

    limit = int(len(split["skin_faces"]) * max_ratio)
    if len(doomed) > limit:
        doomed = doomed[:limit]
    return doomed
