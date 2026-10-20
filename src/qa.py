"""Static and motion QA (runs inside Blender).

Two levels:

  static  - inventory plus skinning sanity (unweighted vertices, bones that
            do not exist, weight sums that are off)
  motion  - drive the rig with a VMD, sample frames and count the garment
            vertices that ended up inside the body.  That is the cheapest
            honest signal for "the body pokes through the clothes".

The P1 acceptance only needs the static level plus a re-import check; the
motion level is the seed of P2.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _is_garment(obj: bpy.types.Object) -> bool:
    return bool(obj.get("mmd_garment", False))


def split_garment(objects: list[bpy.types.Object],
                  garment_materials: list[str] | None = None
                  ) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
    """Split the meshes into garment and body.

    In the live scene the garment carries a marker property.  After a PMX
    round trip that property is gone, so the material names of the selected
    outfit are used instead.
    """
    meshes = [o for o in objects if o.type == 'MESH']
    marked = [o for o in meshes if _is_garment(o)]
    if marked:
        return marked, [o for o in meshes if not _is_garment(o)]
    if not garment_materials:
        return [], meshes
    wanted = set(garment_materials)
    garment = []
    for o in meshes:
        names = {m.name for m in o.data.materials if m}
        if names & wanted:
            garment.append(o)
    return garment, [o for o in meshes if o not in garment]


def skinning_report(objects: list[bpy.types.Object]) -> dict[str, Any]:
    """Unweighted vertices, missing bones and bad weight sums per mesh."""
    armatures = {a.name: {b.name for b in a.data.bones}
                 for a in objects if a.type == 'ARMATURE'}
    out = []
    for ob in objects:
        if ob.type != 'MESH':
            continue
        names = [vg.name for vg in ob.vertex_groups]
        unknown = [n for n in names
                   if armatures and not any(n in s for s in armatures.values())]
        unweighted = 0
        bad_sum = 0
        for v in ob.data.vertices:
            total = sum(g.weight for g in v.groups)
            if total <= 1e-5:
                unweighted += 1
            elif abs(total - 1.0) > 0.02:
                bad_sum += 1
        out.append({
            "object": ob.name,
            "garment": _is_garment(ob),
            "vertices": len(ob.data.vertices),
            "faces": len(ob.data.polygons),
            "vertex_groups": len(names),
            "unknown_bones": unknown[:20],
            "unknown_bone_count": len(unknown),
            "unweighted_vertices": unweighted,
            "bad_weight_sum_vertices": bad_sum,
        })
    return {"meshes": out}


def _evaluated_mesh(obj: bpy.types.Object):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    return obj.evaluated_get(depsgraph).to_mesh(depsgraph=depsgraph,
                                                 preserve_all_data_layers=True)


def _bvh_from_evaluated(obj) -> BVHTree:
    me = _evaluated_mesh(obj)
    verts = [v.co.copy() for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    obj.to_mesh_clear()
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


def motion_check(objects: list[bpy.types.Object], motions: str | None,
                 garment_materials: list[str] | None = None,
                 frame_step: int = 15, sample_stride: int = 3,
                 max_frames: int = 24) -> dict[str, Any]:
    """Drive the rig with a VMD and count garment vertices inside the body."""
    if not motions:
        return {"skipped": "no motion file given"}

    garment, body = split_garment(objects, garment_materials)
    if not garment:
        return {"skipped": "no garment object in the scene"}
    if not body:
        return {"skipped": "no body object in the scene"}

    from . import import_export as ie
    ie.ensure_mmd_tools()

    scene = bpy.context.scene
    arm = next((o for o in objects if o.type == 'ARMATURE'), None)
    if arm is None:
        return {"skipped": "no armature"}

    try:
        bpy.ops.mmd_tools.import_vmd(filepath=motions, scale=0.08,
                                     rename_bones=True, log_level='ERROR')
    except Exception as exc:                        # noqa: BLE001
        return {"error": f"vmd import failed: {type(exc).__name__}: {exc}"}

    start, end = scene.frame_start, scene.frame_end
    frames = list(range(start, end + 1, max(1, frame_step)))[:max_frames]
    results = []
    worst = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        body_bvh = _bvh_from_evaluated(body[0])
        total = 0
        checked = 0
        for g in garment:
            me = _evaluated_mesh(g)
            for i in range(0, len(me.vertices), sample_stride):
                co = me.vertices[i].co
                crossings = _count_crossings(body_bvh, co, Vector((0.0, 0.0, 1.0)))
                if crossings % 2 == 1:
                    total += 1
                checked += 1
            g.to_mesh_clear()
        ratio = total / max(checked, 1)
        results.append({"frame": f, "inside": total, "checked": checked,
                        "ratio": round(ratio, 5)})
        worst.append((ratio, f, total))
    scene.frame_set(start)
    worst.sort(reverse=True)
    return {
        "motion": motions,
        "frame_range": [start, end],
        "sampled_frames": len(frames),
        "per_frame": results,
        "worst_frames": [{"frame": f, "inside": t, "ratio": round(r, 5)}
                          for r, f, t in worst[:5]],
        "max_ratio": round(worst[0][0], 5) if worst else 0.0,
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
    skin = report["skinning"]
    bad = [m for m in skin["meshes"]
           if m["unweighted_vertices"] or m["unknown_bone_count"]]
    items.append({
        "check": "skinning",
        "status": "WARNING" if bad else "OK",
        "detail": f"{len(bad)} mesh(es) with unweighted vertices or unknown bones",
    })
    motion = report["motion"]
    if "max_ratio" in motion:
        items.append({
            "check": "motion",
            "status": "WARNING" if motion["max_ratio"] > 0.01 else "OK",
            "detail": f"max {motion['max_ratio'] * 100:.2f}% of sampled garment "
                      f"vertices inside the body",
        })
    else:
        items.append({"check": "motion", "status": "SKIPPED",
                      "detail": motion.get("skipped", "not run")})
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
