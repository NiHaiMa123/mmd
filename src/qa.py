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

    from . import motion as motion_mod

    split = split_faces(objects, garment_materials)
    gmesh = split["garment_mesh"]
    bmesh_obj = split["body_mesh"]
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
        pierced, checked, _hits = motion_mod._pierce_count(
            motion_mod._bvh_from(bme, split["skin_faces"]),
            motion_mod._bvh_from(gme, split["garment_faces"]),
            bme, split["skin_faces"], rest_sign, stride=sample_stride)
        bev.to_mesh_clear()
        if gev is not bev:
            gev.to_mesh_clear()
        results.append({"frame": f, "pierced": pierced, "checked": checked,
                        "ratio": round(pierced / max(checked, 1), 5)})
    scene.frame_set(start)
    results.sort(key=lambda r: -r["ratio"])
    return {
        "motion": motions,
        "frame_range": [start, end],
        "sampled_frames": len(frames),
        "per_frame": sorted(results, key=lambda r: r["frame"]),
        "worst_frames": results[:5],
        "max_ratio": results[0]["ratio"] if results else 0.0,
    }


def run_qa(objects: list[bpy.types.Object], motions: str | None = None,
           out_dir: str | None = None,
           garment_materials: list[str] | None = None) -> dict[str, Any]:
    from . import import_export as ie

    report: dict[str, Any] = {
        "model": ie.model_info(objects),
        "skinning": skinning_report(objects),
    }
    report["motion"] = motion_check(objects, motions, garment_materials)

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
    else:
        items.append({"check": "motion", "status": "SKIPPED",
                      "detail": motion.get("skipped", motion.get("error", "?"))})
    report["items"] = items
    report["status"] = ("FAILED" if any(i["status"] == "FAILED" for i in items)
                         else "OK")

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "qa_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        report["qa_report"] = str(out / "qa_report.json")
    return report
