"""Clothing extraction: turn selected parts into a standalone garment mesh.

P1-02 of the plan. The source model is never modified: the selected faces are
*copied* into a new mesh that keeps

  * UVs
  * material slots and their textures
  * vertex weights (renamed to the source bone names)
  * shape keys (morphs), re-indexed onto the new vertex numbering
  * a record of the bones / rigid bodies / joints the garment depends on

so P1-03..P1-05 can retarget it and P3 can migrate the physics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy


# --------------------------------------------------------------------------
# Face subset -> standalone mesh
# --------------------------------------------------------------------------


def _copy_shape_keys(src_me, new_obj, used: list[int]) -> list[str]:
    """Copy every shape key (except Basis) onto the new vertex numbering."""
    if not src_me.shape_keys:
        return []
    names = []
    for key in src_me.shape_keys.key_blocks:
        if key.name == src_me.shape_keys.key_blocks[0].name:
            continue
        nk = new_obj.shape_key_add(name=key.name, from_mix=False)
        src_co = [0.0] * (len(src_me.vertices) * 3)
        key.data.foreach_get("co", src_co)
        sub = []
        for old in used:
            sub.extend(src_co[old * 3:old * 3 + 3])
        if len(sub) == len(nk.data) * 3:
            nk.data.foreach_set("co", sub)
        names.append(key.name)
    return names


def _copy_vertex_groups(src_obj, new_obj, used: list[int]) -> list[str]:
    """Rebuild the vertex groups on the new numbering.

    `MeshVertex.groups` already carries (group index, weight) per vertex, so we
    can rebuild without walking every group x every vertex.
    """
    src_me = src_obj.data
    group_names = [vg.name for vg in src_obj.vertex_groups]
    buckets: dict[str, dict[float, list[int]]] = {}

    for new_index, old_index in enumerate(used):
        for g in src_me.vertices[old_index].groups:
            if g.weight <= 0.0:
                continue
            name = group_names[g.group]
            key = round(g.weight, 6)
            buckets.setdefault(name, {}).setdefault(key, []).append(new_index)

    out = []
    for name, by_weight in buckets.items():
        vg = new_obj.vertex_groups.new(name=name)
        for weight, indices in by_weight.items():
            vg.add(indices, weight, 'REPLACE')
        out.append(name)
    return out


def _copy_mesh_subset(src_obj, face_ids: list[int], name: str) -> tuple[bpy.types.Object, list[int]]:
    """Build a new mesh object from a subset of faces of `src_obj`."""
    src_me = src_obj.data
    used = sorted({v for fid in face_ids for v in src_me.polygons[fid].vertices})
    vmap = {old: new for new, old in enumerate(used)}

    verts = [tuple(src_me.vertices[i].co) for i in used]
    faces = [[vmap[v] for v in src_me.polygons[fid].vertices] for fid in face_ids]

    new_me = bpy.data.meshes.new(name)
    new_me.from_pydata(verts, [], faces)
    new_me.update()

    new_obj = bpy.data.objects.new(name, new_me)
    bpy.context.scene.collection.objects.link(new_obj)
    new_obj.matrix_world = src_obj.matrix_world.copy()

    # --- materials (keep only the ones actually used) ---
    slot_map: dict[int, int] = {}
    for fid in face_ids:
        si = src_me.polygons[fid].material_index
        if si not in slot_map:
            slot_map[si] = len(new_me.materials)
            new_me.materials.append(src_me.materials[si])
    for k, fid in enumerate(face_ids):
        new_me.polygons[k].material_index = slot_map[src_me.polygons[fid].material_index]
        new_me.polygons[k].use_smooth = src_me.polygons[fid].use_smooth

    # --- UVs ---
    uv_src = src_me.uv_layers.active
    if uv_src is not None:
        uv_new = new_me.uv_layers.new(name=uv_src.name)
        base = 0
        for fid in face_ids:
            src_poly = src_me.polygons[fid]
            n = len(src_poly.loop_indices)
            for j, li in enumerate(src_poly.loop_indices):
                uv_new.data[base + j].uv = uv_src.data[li].uv
            base += n

    # --- weights and morphs ---
    groups = _copy_vertex_groups(src_obj, new_obj, used)
    morphs = _copy_shape_keys(src_me, new_obj, used)

    new_obj["mmd_extracted_from"] = src_obj.name
    new_obj["mmd_extracted_morphs"] = ",".join(morphs)
    new_obj["mmd_extracted_groups"] = ",".join(groups)
    new_obj["mmd_garment"] = True
    return new_obj, used


# --------------------------------------------------------------------------
# Dependency inventory
# --------------------------------------------------------------------------


def collect_dependencies(objects: list[bpy.types.Object], cloth: list[bpy.types.Object],
                         used_bones: set[str]) -> dict[str, Any]:
    """Bones / morphs / rigid bodies / joints the garment depends on."""
    from . import import_export as ie

    # bone hierarchy for the used bones
    bone_info: dict[str, Any] = {}
    for ob in objects:
        if ob.type != 'ARMATURE':
            continue
        for b in ob.data.bones:
            if b.name in used_bones and b.name not in bone_info:
                bone_info[b.name] = {
                    "parent": b.parent.name if b.parent else None,
                    "head": [round(v, 5) for v in b.head_local],
                    "tail": [round(v, 5) for v in b.tail_local],
                }
        break

    rigid_bodies = []
    joint_objs = []
    for ob in objects:
        mt = getattr(ob, "mmd_type", "NONE")
        if mt == "RIGID_BODY":
            rb = ob.mmd_rigid
            if rb.bone and rb.bone not in used_bones:
                continue
            rigid_bodies.append({
                "name": ob.name,
                "bone": rb.bone,
                "type": rb.type,
                "shape": rb.shape,
                "size": [round(v, 4) for v in rb.size],
                "collision_group": rb.collision_group_number,
                "collision_mask": list(rb.collision_group_mask),
            })
        elif mt == "JOINT":
            joint_objs.append(ob)

    rigid_names = {r["name"] for r in rigid_bodies}
    joints = []
    for ob in joint_objs:
        rbc = ob.rigid_body_constraint
        o1 = rbc.object1.name if rbc and rbc.object1 else None
        o2 = rbc.object2.name if rbc and rbc.object2 else None
        if o1 not in rigid_names and o2 not in rigid_names:
            continue
        joints.append({
            "name": ob.name,
            "name_j": ob.mmd_joint.name_j,
            "object1": o1,
            "object2": o2,
            "spring_linear": [round(v, 4) for v in ob.mmd_joint.spring_linear],
            "spring_angular": [round(v, 4) for v in ob.mmd_joint.spring_angular],
        })

    # material morphs (not vertex based) live on the model root
    material_morphs = []
    for ob in objects:
        if getattr(ob, "mmd_type", "NONE") != "ROOT":
            continue
        for m in getattr(ob.mmd_root, "morphs", []):
            material_morphs.append({
                "name": m.name,
                "type": getattr(m, "type", "?"),
                "category": getattr(m, "category", ""),
            })
        break

    return {
        "bones": bone_info,
        "rigid_bodies": rigid_bodies,
        "joints": joints,
        "material_morphs": material_morphs,
        "cloth_objects": [o.name for o in cloth],
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def extract_clothing(objects: list[bpy.types.Object], parts: list[dict[str, Any]],
                     selected_part_ids: list[int], out_dir: str,
                     name: str = "Cloth") -> dict[str, Any]:
    """Copy the selected parts into a standalone garment and report the deps."""
    from . import import_export as ie

    meshes = ie.model_meshes(objects)
    selected = set(selected_part_ids)
    faces_by_mesh: dict[str, list[int]] = {}
    for p in parts:
        if p["id"] in selected:
            faces_by_mesh.setdefault(p["mesh"], []).extend(p["faces"])

    if not faces_by_mesh:
        raise RuntimeError("no parts selected - nothing to extract")

    cloth = []
    used_bones: set[str] = set()
    for ob in meshes:
        if ob.name not in faces_by_mesh:
            continue
        face_ids = sorted(set(faces_by_mesh[ob.name]))
        new_obj, _used = _copy_mesh_subset(ob, face_ids, name)
        groups = new_obj.get("mmd_extracted_groups", "")
        used_bones.update(g for g in groups.split(",") if g)
        cloth.append(new_obj)

    # bind to the source armature so the garment still deforms with the source rig
    for arm in (o for o in objects if o.type == 'ARMATURE'):
        for c in cloth:
            mod = c.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = arm
            c.parent = arm
            c.parent_type = 'OBJECT'
            c.matrix_parent_inverse = arm.matrix_world.inverted()
        break

    deps = collect_dependencies(objects, cloth, used_bones)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "dependencies.json").write_text(
        json.dumps(deps, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {
        "cloth_objects": [
            {"name": c.name,
             "vertices": len(c.data.vertices),
             "faces": len(c.data.polygons),
             "materials": [m.name if m else None for m in c.data.materials],
             "shape_keys": [k.name for k in
                            (c.data.shape_keys.key_blocks if c.data.shape_keys else [])],
             "vertex_groups": len(c.vertex_groups)}
            for c in cloth],
        "used_bones": sorted(used_bones),
        "rigid_body_count": len(deps["rigid_bodies"]),
        "joint_count": len(deps["joints"]),
        "dependencies_json": str(out / "dependencies.json"),
    }
    return {"cloth": cloth, "summary": summary, "deps": deps}
