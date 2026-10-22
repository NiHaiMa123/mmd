"""Static and motion QA (runs inside Blender).

Two levels:

  static  - inventory plus skinning sanity (unweighted vertices, bones that
            do not exist, weight sums that are off)
  motion  - drive the rig with a VMD, sample frames and count the garment
            vertices that ended up inside the body.  That is the cheapest
            honest signal for "the body pokes through the clothes".

A PMX model is a single mesh, so after an export the clothes and the body
share one object - the split therefore happens on *faces*, by material.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HAIR_WORDS = ("髪", "发", "髮", "辫", "髻", "hair", "bang")
FACE_WORDS = ("面", "顔", "目", "眼", "眉", "睫", "口", "舌", "鼻",
              "face", "eye", "brow", "lash", "mouth", "tongue")


def _is_garment(obj: bpy.types.Object) -> bool:
    return bool(obj.get("mmd_garment", False))


def _mat_name(obj: bpy.types.Object, poly) -> str:
    me = obj.data
    mi = poly.material_index
    if mi < len(me.materials) and me.materials[mi]:
        return me.materials[mi].name
    return ""


def split_faces(objects: list[bpy.types.Object],
                garment_materials: list[str] | None
                ) -> dict[str, Any]:
    """Split the model into garment faces and skin faces.

    Works both on the live scene (the garment is its own object) and on a
    re-imported PMX (one mesh, split by material).
    """
    from . import import_export as ie

    meshes = ie.model_meshes(objects)
    marked = [o for o in meshes if _is_garment(o)]
    if marked:
        g = marked[0]
        bodies = [o for o in meshes if o is not g]
        body = bodies[0] if bodies else None
        skin, hair = [], []
        if body is not None:
            for p in body.data.polygons:
                low = _mat_name(body, p).lower()
                if any(w in low for w in HAIR_WORDS) or \
                        any(w in low for w in FACE_WORDS):
                    hair.append(p.index)
                else:
                    skin.append(p.index)
        return {"garment_mesh": g, "body_mesh": body,
                "garment_faces": list(range(len(g.data.polygons))),
                "skin_faces": skin, "hair_faces": hair}

    wanted = set(garment_materials or [])
    for m in meshes:
        me = m.data
        gfaces, bfaces, hairfaces = [], [], []
        for p in me.polygons:
            name = _mat_name(m, p)
            if wanted and name in wanted:
                gfaces.append(p.index)
            else:
                low = name.lower()
                if any(w in low for w in HAIR_WORDS):
                    hairfaces.append(p.index)
                elif any(w in low for w in FACE_WORDS):
                    hairfaces.append(p.index)
                else:
                    bfaces.append(p.index)
        if gfaces:
            return {"garment_mesh": m, "body_mesh": m,
                    "garment_faces": gfaces,
                    "skin_faces": bfaces, "hair_faces": hairfaces}
    # no garment found - fall back to the whole body as skin
    if meshes:
        m = meshes[0]
        return {"garment_mesh": None, "body_mesh": m, "garment_faces": [],
                "skin_faces": list(range(len(m.data.polygons))),
                "hair_faces": []}
    return {"garment_mesh": None, "body_mesh": None, "garment_faces": [],
            "skin_faces": [], "hair_faces": []}


AUX_GROUP_PREFIXES = ("mmd_", "UV_", "_")


def _is_aux_group(name: str) -> bool:
    """mmd_tools helper groups: SDEF control points, UV morphs, dummy bones.

    They carry weights of their own, so they must not be counted when the
    skinning weight sum is checked.
    """
    return name.startswith(AUX_GROUP_PREFIXES)


def skinning_report(objects: list[bpy.types.Object]) -> dict[str, Any]:
    """Unweighted vertices, missing bones and bad weight sums per mesh."""
    from . import import_export as ie

    armatures = {a.name: {b.name for b in a.data.bones}
                 for a in objects if a.type == 'ARMATURE'}
    out = []
    for ob in ie.model_meshes(objects):
        names = [vg.name for vg in ob.vertex_groups]
        unknown = [n for n in names
                   if not _is_aux_group(n)
                   and armatures and not any(n in s for s in armatures.values())]
        unweighted = 0
        bad_sum = 0
        samples = []
        for v in ob.data.vertices:
            total = sum(g.weight for g in v.groups
                        if not _is_aux_group(names[g.group]))
            if total <= 1e-5:
                unweighted += 1
            elif abs(total - 1.0) > 0.02:
                bad_sum += 1
                if len(samples) < 5:
                    samples.append(round(total, 5))
        out.append({
            "object": ob.name,
            "garment": _is_garment(ob),
            "vertices": len(ob.data.vertices),
            "faces": len(ob.data.polygons),
            "vertex_groups": len(names),
            "aux_groups": sum(1 for n in names if _is_aux_group(n)),
            "unknown_bones": unknown[:20],
            "unknown_bone_count": len(unknown),
            "unweighted_vertices": unweighted,
            "bad_weight_sum_vertices": bad_sum,
            "bad_weight_sum_samples": samples,
        })
    return {"meshes": out}


def _evaluated_mesh(obj: bpy.types.Object):
    """Evaluate a mesh and return (mesh, owner).

    to_mesh_clear() has to be called on the *evaluated* object - doing it on
    the original frees the mesh the depsgraph is using.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    me = ev.to_mesh(depsgraph=depsgraph, preserve_all_data_layers=True)
    return me, ev


def _evaluated_mesh_copy(obj: bpy.types.Object):
    """Take the evaluated mesh out of the depsgraph as an independent copy.

    new_from_object does *not* apply the modifiers: the copy stays in the
    rest pose.  With the physics on that is fatal - every frame would measure
    the same rest pose, the clothes would never move relative to the body and
    the piercing count would stay at zero for the wrong reason.  to_mesh()
    gives the deformed mesh, copy() takes it away from the depsgraph so the
    physics handler cannot invalidate it in the next frame.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(depsgraph)
    src = ev.to_mesh(depsgraph=depsgraph, preserve_all_data_layers=True)
    me = src.copy()
    ev.to_mesh_clear()
    return me, ev


def _bvh(obj: bpy.types.Object, face_indices: list[int]) -> BVHTree:
    me, oev = _evaluated_mesh(obj)
    verts = [v.co.copy() for v in me.vertices]
    polys = [list(me.polygons[i].vertices) for i in face_indices
             if i < len(me.polygons)]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    oev.to_mesh_clear()
    return bvh


def _count_crossings(bvh: BVHTree, origin: Vector, direction: Vector,
                      max_dist: float = 3.0) -> int:
    count = 0
    o = origin.copy()
    d = direction.normalized()
    remaining = max_dist
    while remaining > 1e-5:
        loc, _n, _i, dist = bvh.ray_cast(o, d, remaining)
        if loc is None:
            break
        count += 1
        step = dist + 1e-4
        o = loc + d * step
        remaining -= step
        if count > 32:
            break
    return count


_CHECK_DIRS = (
    Vector((0.0, 0.0, 1.0)), Vector((0.0, 0.0, -1.0)),
    Vector((1.0, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)),
    Vector((0.0, 1.0, 0.0)), Vector((0.0, -1.0, 0.0)),
)


def _inside(bvh: BVHTree, point: Vector, max_dist: float = 3.0) -> bool:
    """Is the point inside the (closed) body?

    A single ray is not enough once the body has holes - the mask deletes the
    covered faces, and a ray leaving through such a hole breaks the parity.
    Voting over six directions survives that.
    """
    odd = 0
    for d in _CHECK_DIRS:
        if _count_crossings(bvh, point, d, max_dist) % 2 == 1:
            odd += 1
    return odd > len(_CHECK_DIRS) / 2


def _rigid_bvh(r: bpy.types.Object):
    """The collision shape of a rigid body, as a BVH in world space.

    The collider meshes are closed solids, so the parity test works on them
    even where the body mesh itself has holes.  That makes them the honest
    reference for "the skirt is inside the leg".
    """
    me = r.data
    if me is None or not len(me.vertices) or not len(me.polygons):
        return None
    mw = r.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    center = Vector((0.0, 0.0, 0.0))
    for v in verts:
        center += v
    center /= len(verts)
    radius = max((v - center).length for v in verts)
    return bvh, center, radius


def _cloth_inside_colliders(cloth_me, gfaces: list[int],
                            colliders: list[tuple[str, BVHTree, Vector, float]],
                            stride: int = 4,
                            world=None) -> tuple[int, int, dict[str, int]]:
    """How many garment vertices ended up inside one of the colliders.

    This is the other direction of the clipping: the body piercing the clothes
    is measured by the sign flip, but "the skirt passes through the leg" is
    the garment ending up inside the leg.  The colliders are the honest
    reference for that - the body mesh has holes where the mask deleted the
    covered faces, the collision shapes do not.

    The colliders are built in world space, so the garment's vertices have to
    be transformed as well.  `world` is the garment object's matrix.
    """
    verts = set()
    for fi in gfaces:
        if fi < len(cloth_me.polygons):
            verts.update(cloth_me.polygons[fi].vertices)
    total = 0
    checked = 0
    per_bone: dict[str, int] = {}
    for i in sorted(verts)[::stride]:
        co = cloth_me.vertices[i].co
        if world is not None:
            co = world @ co
        checked += 1
        for bone, bvh, center, radius in colliders:
            if (co - center).length > radius:
                continue
            if _inside(bvh, co):
                total += 1
                per_bone[bone] = per_bone.get(bone, 0) + 1
                break
    return total, checked, per_bone


# Where a body point is, so a piercing report can be read per body part.
# The overall ratio says "something is wrong"; the breakdown says where.
# The names are matched exactly: a prefix match on 足 also catches 足D (a hip
# helper) and 足回転+ (the ankle), and those are not the foot.
REGION_RULES = (
    ("hand", ("人指１", "人指２", "人指３", "中指１", "中指２", "中指３",
              "薬指１", "薬指２", "薬指３", "小指１", "小指２", "小指３",
              "親指０", "親指１", "親指２", "手首", "手捩", "手捩1", "手捩2")),
    ("foot", ("足先EX", "つま先", "足先",
              "足親指０", "足親指１",
              "足人指１", "足人指２", "足中指１", "足中指２",
              "足薬指１", "足薬指２", "足小指１", "足小指２")),
    ("head", ("頭", "首")),
    ("arm", ("肩", "腕", "ひじ")),
    ("torso", ("胸", "上半身", "腹", "背")),
    ("leg", ("ひざ", "ひざD", "ひざD+", "ひざD++", "足回転", "足回転+",
             "足回転++", "足首", "足首D", "足首D+", "足首D++")),
    ("waist", ("腰", "下半身", "尻", "足D", "足D+", "足D++", "腿")),
)


def body_region(bone_name: str) -> str:
    """The body part a bone belongs to.

    The names are matched exactly.  A prefix match is what put the hip helper
    足D and the ankle 足回転+ into the "foot" column and made the feet look
    like the worst part of the model.
    """
    base = bone_name.split(".")[0]
    for region, names in REGION_RULES:
        if base in names:
            return region
    return "other"


def _region_candidates(body_me, bfaces: list[int], region_of: list[str],
                       rest_sign: dict[int, float], stride: int
                       ) -> tuple[dict[str, int], dict[str, int], dict[str, int],
                                  dict[str, int]]:
    """How many skin points every region puts into the test.

    "0 points pierced in the foot" only means something next to "12 points
    of the foot were looked at" - a region with no candidates cannot pierce
    anything.  The points are counted apart by what the detector can do
    with them:

    * `positive`: the rest sign is above the threshold, so a sign flip can
      be judged at all;
    * `nonpositive`: the rest sign is there but too small or negative - the
      detector never counts these, so they are not really candidates;
    * `missing`: no rest sign at all.
    """
    totals: dict[str, int] = {}
    positive: dict[str, int] = {}
    nonpositive: dict[str, int] = {}
    missing: dict[str, int] = {}
    verts = set()
    for fi in bfaces:
        if fi < len(body_me.polygons):
            verts.update(body_me.polygons[fi].vertices)
    for i in sorted(verts)[::stride]:
        key = region_of[i] if i < len(region_of) else "other"
        totals[key] = totals.get(key, 0) + 1
        if i not in rest_sign:
            missing[key] = missing.get(key, 0) + 1
        elif rest_sign[i] > 0.001:
            positive[key] = positive.get(key, 0) + 1
        else:
            nonpositive[key] = nonpositive.get(key, 0) + 1
    return totals, positive, nonpositive, missing


def motion_check(objects: list[bpy.types.Object], motions: str | None,
                 garment_materials: list[str] | None = None,
                 frame_step: int = 15, sample_stride: int = 3,
                 max_frames: int = 24) -> dict[str, Any]:
    """Drive the rig with a VMD and count the body points that pierce the clothes.

    The parity test ("is this point inside the body") cannot be used here:
    the body has holes where the mask removed the covered faces.  The sign
    flip test of the motion module survives that, so the same measure is
    used - the body points that came out through the clothes.
    """
    if not motions:
        return {"skipped": "no motion file given"}

    from . import dressing
    from . import motion as motion_mod

    split = split_faces(objects, garment_materials)
    gmesh = split["garment_mesh"]
    bmesh_obj = split["body_mesh"]
    region_of: list[str] = []
    for name in dressing.dominant_bones(bmesh_obj):
        region_of.append(body_region(name))
    if gmesh is None or bmesh_obj is None:
        return {"skipped": "model has no garment/skin split"}
    if not split["garment_faces"] or not split["skin_faces"]:
        return {"skipped": "model has no garment/skin split"}

    from . import import_export as ie
    ie.ensure_mmd_tools()

    scene = bpy.context.scene
    if not any(o.type == 'ARMATURE' for o in objects):
        return {"skipped": "no armature"}

    # reference: in the rest pose the clothes are always outside the body
    bme, bev = _evaluated_mesh(bmesh_obj)
    if gmesh is bmesh_obj:
        gme, gev = bme, bev
    else:
        gme, gev = _evaluated_mesh(gmesh)
    rest_sign = motion_mod.rest_side_signs(
        motion_mod._bvh_from(bme, split["skin_faces"]),
        motion_mod._bvh_from(gme, split["garment_faces"]),
        bme, split["skin_faces"])
    # how many points every region puts into the test - the mesh is freed
    # right after, so this has to happen now
    (candidates, ref_positive, ref_nonpositive,
     ref_missing) = _region_candidates(
        bme, split["skin_faces"], region_of, rest_sign, sample_stride)
    bev.to_mesh_clear()
    if gev is not bev:
        gev.to_mesh_clear()

    try:
        bpy.ops.mmd_tools.import_vmd(filepath=motions, scale=0.08,
                                     rename_bones=True, log_level='ERROR')
    except Exception as exc:                        # noqa: BLE001
        return {"error": f"vmd import failed: {type(exc).__name__}: {exc}"}

    start, end = scene.frame_start, scene.frame_end
    frames = list(range(start, end + 1, max(1, frame_step)))[:max_frames]
    results = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        bme, bev = _evaluated_mesh(bmesh_obj)
        if gmesh is bmesh_obj:
            gme, gev = bme, bev
        else:
            gme, gev = _evaluated_mesh(gmesh)
        pierced, checked, hits = motion_mod._pierce_count(
            motion_mod._bvh_from(bme, split["skin_faces"]),
            motion_mod._bvh_from(gme, split["garment_faces"]),
            bme, split["skin_faces"], rest_sign, stride=sample_stride)
        bev.to_mesh_clear()
        if gev is not bev:
            gev.to_mesh_clear()
        per_region: dict[str, int] = {}
        for i in hits:
            key = region_of[i] if i < len(region_of) else "other"
            per_region[key] = per_region.get(key, 0) + 1
        results.append({"frame": f, "pierced": pierced, "checked": checked,
                        "ratio": round(pierced / max(checked, 1), 5),
                        "regions": per_region})
    scene.frame_set(start)
    results.sort(key=lambda r: -r["ratio"])
    worst = results[0] if results else {}
    totals: dict[str, int] = {}
    for r in results:
        for key, n in r.get("regions", {}).items():
            totals[key] = totals.get(key, 0) + n
    return {
        "pierced_by_region": dict(sorted(totals.items(),
                                         key=lambda kv: -kv[1])),
        "candidates_by_region": dict(sorted(candidates.items(),
                                           key=lambda kv: -kv[1])),
        # the points the detector can actually judge: a rest sign that is
        # there but too small or negative never counts as a sign flip, so
        # it is not a candidate
        "reference_positive_by_region": dict(sorted(ref_positive.items(),
                                                   key=lambda kv: -kv[1])),
        "reference_nonpositive_by_region": dict(sorted(ref_nonpositive.items(),
                                                       key=lambda kv: -kv[1])),
        "missing_reference_by_region": dict(sorted(ref_missing.items(),
                                                   key=lambda kv: -kv[1])),
        "worst_frame_regions": worst.get("regions", {}),
        "motion": motions,
        "frame_range": [start, end],
        "sampled_frames": len(frames),
        "per_frame": sorted(results, key=lambda r: r["frame"]),
        "worst_frames": results[:5],
        "max_ratio": results[0]["ratio"] if results else 0.0,
    }


def physics_motion_check(objects: list[bpy.types.Object], motions: str,
                         garment_materials: list[str] | None,
                         first_frame: int = 340, last_frame: int = 420,
                         break_collision: bool = False,
                         outfit_groups: list[int] | None = None
                         ) -> dict[str, Any]:
    """Count the body points that pierce the clothes *with* the physics on.

    The normal motion check only evaluates the rig, so it measures the
    clipping of a model whose physics never runs.  This one maps the MMD
    collision groups onto Blender's rigid body world, lets Bullet run and
    writes the simulated motion back onto the bones, which is what MMD does.

    `break_collision` switches the outfit off the base body's limbs again -
    that is the state before the collision groups were translated, and it
    makes the two runs comparable.
    """
    from . import dressing, motion as motion_mod, physics_sim

    split = split_faces(objects, garment_materials)
    gmesh = split["garment_mesh"]
    bmesh_obj = split["body_mesh"]
    if gmesh is None or bmesh_obj is None:
        return {"skipped": "model has no garment/skin split"}
    if not split["garment_faces"] or not split["skin_faces"]:
        return {"skipped": "model has no garment/skin split"}

    scene = bpy.context.scene
    arm = next((o for o in objects if o.type == "ARMATURE"), None)
    if arm is None:
        return {"skipped": "model has no armature"}

    # the rest signs, taken while the rig is still in its rest pose
    bme, bev = _evaluated_mesh_copy(bmesh_obj)
    if gmesh is bmesh_obj:
        gme, gev = bme, bev
    else:
        gme, gev = _evaluated_mesh_copy(gmesh)
    if not split["garment_faces"] or not split["skin_faces"]:
        return {"skipped": "garment/skin split is empty",
                "garment_faces": len(split["garment_faces"]),
                "skin_faces": len(split["skin_faces"])}
    rest_sign = motion_mod.rest_side_signs(
        motion_mod._bvh_from(bme, split["skin_faces"]),
        motion_mod._bvh_from(gme, split["garment_faces"]),
        bme, split["skin_faces"])
    dom = dressing.dominant_bones(bmesh_obj)
    # the same denominators as the plain motion check, so the two reports
    # can be read next to each other
    region_of = [body_region(name) for name in dom]
    (candidates, ref_positive, ref_nonpositive,
     ref_missing) = _region_candidates(
        bme, split["skin_faces"], region_of, rest_sign, 3)
    bpy.data.meshes.remove(bme)
    if gme is not bme:
        bpy.data.meshes.remove(gme)

    try:
        bpy.ops.mmd_tools.import_vmd(filepath=motions, scale=0.08,
                                     rename_bones=True, log_level="ERROR")
    except Exception as exc:                        # noqa: BLE001
        return {"error": f"vmd import failed: {type(exc).__name__}: {exc}"}

    # The counterfactual is decided before the simulation starts: the outfit
    # is taken off the base body's limbs while the collision layers are
    # built, not afterwards.  A switched mask on a warm cache is not the same
    # model, and comparing the two would compare two different simulations.
    # The contact matrix wants the state *before* the simulation moves the
    # bodies around, so their positions are read here and not afterwards.
    from . import physics_sim as _ps
    _rigids = [o for o in bpy.data.objects
               if getattr(o, "mmd_type", "NONE") == "RIGID_BODY"]
    # the bodies were just imported: without a depsgraph update their
    # matrices are still the identity and every pair would count as "near"
    bpy.context.view_layer.update()
    rest_positions = {o.name: o.matrix_world.translation.copy()
                      for o in _rigids}
    setup = physics_sim.setup(scene, arm, first_frame, last_frame,
                              outfit_groups=set(outfit_groups or []),
                              break_outfit_body=break_collision)
    broken_info: dict[str, Any] = {}
    if break_collision:
        broken_info = {"outfit_groups": sorted(set(outfit_groups or [])),
                       "broken_mask_bits": setup.get("broken_mask_bits", 0)}
    # the contact matrix has to describe the state this run actually used
    setup["contact_matrix"] = _ps.contact_matrix_report(
        _rigids, positions=rest_positions)

    results = []
    sample = set(range(first_frame, last_frame + 1, 15))
    # the collision shapes of the base body: the garment has to stay outside
    # of them, so the vertices that end up inside are the skirt passing
    # through the legs
    outfit_set = set(outfit_groups or [])
    body_rigids = [o for o in bpy.data.objects
                   if getattr(o, "mmd_type", "NONE") == "RIGID_BODY"
                   and o.mmd_rigid.collision_group_number not in outfit_set]
    # the simulation has to run through: bullet only advances when the frame
    # moves on from the point cache start, and resetting the cache every frame
    # would leave the outfit standing still.
    cache = scene.rigidbody_world.point_cache
    if cache.frame_start != first_frame:
        cache.frame_start = first_frame
    scene.frame_set(first_frame)
    scene.view_layers[0].update()
    first_pos: list | None = None
    last_pos: list | None = None
    # the dynamic near field: the pairs that come close *during* the action,
    # not only in the rest pose.  The rules do not change while the
    # simulation runs, so the pair table is built once.
    pair_table = _ps._pair_table(_rigids)
    dynamic_near: list[dict[str, Any]] = []
    sample_lo, sample_hi = min(sample), max(sample)
    for f in range(first_frame, last_frame + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        if f not in sample:
            continue
        # where the bodies are in this frame
        frame_positions = {o.name: o.matrix_world.translation.copy()
                           for o in _rigids}
        near = _ps.contact_matrix_report(_rigids, positions=frame_positions,
                                         table=pair_table)
        dynamic_near.append({
            "frame": f,
            "near_pairs": near["near_pairs"],
            "near_false_positive": near["near_false_positive"],
            "near_false_negative": near["near_false_negative"],
            "near_gap_pairs": near["near_gap_pairs"],
            "near_gap_false_positive": near["near_gap_false_positive"],
            "near_gap_false_negative": near["near_gap_false_negative"],
        })
        bme, bev = _evaluated_mesh_copy(bmesh_obj)
        if gmesh is bmesh_obj:
            gme, gev = bme, bev
        else:
            gme, gev = _evaluated_mesh_copy(gmesh)
        # the evaluated geometry has to change at all, otherwise the numbers
        # below are measured on a model that never moved
        step = max(1, len(gme.vertices) // 400)
        snapshot = [gme.vertices[i].co.copy()
                    for i in range(0, len(gme.vertices), step)]
        if f == sample_lo:
            first_pos = snapshot
        if f == sample_hi:
            last_pos = snapshot
        pierced, checked, hits = motion_mod._pierce_count(
            motion_mod._bvh_from(bme, split["skin_faces"]),
            motion_mod._bvh_from(gme, split["garment_faces"]),
            bme, split["skin_faces"], rest_sign, stride=3)
        # the garment inside the base body's collision shapes
        colliders = []
        for o in body_rigids:
            bvh = _rigid_bvh(o)
            if bvh:
                colliders.append((o.mmd_rigid.bone or "?", *bvh))
        in_body, in_checked, in_by_bone = _cloth_inside_colliders(
            gme, split["garment_faces"], colliders, world=gmesh.matrix_world)
        in_leg = sum(n for bone, n in in_by_bone.items()
                     if body_region(bone) in ("leg", "foot"))
        bpy.data.meshes.remove(bme)
        if gme is not bme:
            bpy.data.meshes.remove(gme)
        regions: dict[str, int] = {}
        for i in hits:
            key = body_region(dom[i]) if i < len(dom) else "other"
            regions[key] = regions.get(key, 0) + 1
        results.append({"frame": f, "pierced": pierced, "checked": checked,
                        "ratio": round(pierced / max(checked, 1), 5),
                        "regions": regions,
                        # the colliders are loose proxies: a garment inside one
                        # is a physics diagnosis, not a visible penetration
                        "proxy_in_body": in_body,
                        "proxy_in_body_checked": in_checked,
                        "proxy_in_leg": in_leg,
                        "proxy_in_body_by_bone": in_by_bone})
    totals: dict[str, int] = {}
    for r in results:
        for key, n in r["regions"].items():
            totals[key] = totals.get(key, 0) + n
    garment_motion = 0.0
    if first_pos and last_pos and len(first_pos) == len(last_pos):
        garment_motion = max((a - b).length for a, b in zip(first_pos, last_pos))
    return {
        "physics": True,
        "break_collision": break_collision,
        "broken": broken_info,
        "frames": [first_frame, last_frame],
        "setup": setup,
        "per_frame": results,
        "candidates_by_region": dict(sorted(candidates.items(),
                                           key=lambda kv: -kv[1])),
        "reference_positive_by_region": dict(sorted(ref_positive.items(),
                                                   key=lambda kv: -kv[1])),
        "reference_nonpositive_by_region": dict(sorted(ref_nonpositive.items(),
                                                       key=lambda kv: -kv[1])),
        "missing_reference_by_region": dict(sorted(ref_missing.items(),
                                                   key=lambda kv: -kv[1])),
        # the near field during the action, per sampled frame
        "dynamic_near_field": dynamic_near,
        "dynamic_near_gap_pairs_max": max(
            (d["near_gap_pairs"] for d in dynamic_near), default=0),
        "dynamic_near_gap_false_positive_max": max(
            (d["near_gap_false_positive"] for d in dynamic_near), default=0),
        "dynamic_near_gap_false_negative_max": max(
            (d["near_gap_false_negative"] for d in dynamic_near), default=0),
        "pierced_by_region": dict(sorted(totals.items(),
                                         key=lambda kv: -kv[1])),
        "proxy_in_body_total": sum(r["proxy_in_body"] for r in results),
        "proxy_in_leg_total": sum(r["proxy_in_leg"] for r in results),
        "max_ratio": max((r["ratio"] for r in results), default=0.0),
        # data integrity: if the evaluated geometry never moved, every number
        # above was measured on a model that stood still
        "garment_motion": round(garment_motion, 6),
        "no_motion": garment_motion < 1e-4,
    }


def run_qa(objects: list[bpy.types.Object], motions: str | None = None,
           out_dir: str | None = None,
           garment_materials: list[str] | None = None,
           physics: bool = False,
           break_collision: bool = False,
           outfit_groups: list[int] | None = None) -> dict[str, Any]:
    from . import import_export as ie

    report: dict[str, Any] = {
        "model": ie.model_info(objects),
        "skinning": skinning_report(objects),
    }
    report["motion"] = (physics_motion_check(objects, motions, garment_materials,
                                             break_collision=break_collision,
                                             outfit_groups=outfit_groups)
                        if physics else
                        motion_check(objects, motions, garment_materials))

    items = []
    skin = report["skinning"]["meshes"]
    bad = [m for m in skin if m["unweighted_vertices"] or m["unknown_bone_count"]]
    items.append({
        "check": "skinning",
        "status": "WARNING" if bad else "OK",
        "detail": f"{len(bad)} mesh(es) with unweighted vertices or unknown bones",
    })
    motion = report["motion"]
    if "max_ratio" in motion:
        items.append({
            "check": "motion",
            "status": "WARNING" if motion["max_ratio"] > 0.005 else "OK",
            "detail": f"max {motion['max_ratio'] * 100:.2f}% of sampled body "
                      f"points pierce through the clothes",
        })
        if motion.get("no_motion"):
            # the evaluated geometry never changed: the numbers above were
            # measured on a model that stood still, so they mean nothing
            items.append({
                "check": "motion_data",
                "status": "FAILED",
                "detail": "the evaluated model did not move - the measurement "
                          "has no data behind it",
            })
    else:
        items.append({"check": "motion", "status": "SKIPPED",
                      "detail": motion.get("skipped", motion.get("error", "?"))})
    report["items"] = items
    # "no piercing found" is not the same as "the check ran and found
    # nothing": a check that did not run has to be UNKNOWN, not OK.  A run
    # without a motion file did not ask for the motion check, so that is
    # not a gap.
    if any(i["status"] == "FAILED" for i in items):
        report["status"] = "FAILED"
    elif motions and any(i["status"] == "SKIPPED" for i in items):
        report["status"] = "UNKNOWN"
    elif any(i["status"] == "WARNING" for i in items):
        report["status"] = "WARNING"
    else:
        report["status"] = "OK"

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "qa_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["qa_report"] = str(out / "qa_report.json")
    return report
