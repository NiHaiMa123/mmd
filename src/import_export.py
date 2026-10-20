"""PMX import / export / inspection (runs inside Blender).

Only the pieces that need bpy live here; the outer CLI never imports this.
"""
from __future__ import annotations

import os
from typing import Any

import bpy

# mmd_tools ships either as a Blender extension (4.2+) or as a legacy addon.
MMD_TOOLS_MODULES = (
    "bl_ext.blender_org.mmd_tools",
    "mmd_tools",
)

# mmd_tools' import/export scales are inverses of each other.
IMPORT_SCALE = 0.08
EXPORT_SCALE = 12.5


class MmdToolsMissing(RuntimeError):
    pass


def ensure_mmd_tools() -> str:
    """Enable mmd_tools (as extension or legacy addon) and return the module name."""
    for mod in MMD_TOOLS_MODULES:
        try:
            bpy.ops.preferences.addon_enable(module=mod)
        except Exception:
            continue
        if hasattr(bpy.ops.mmd_tools, "import_model"):
            return mod
    raise MmdToolsMissing(
        "mmd_tools is not available. Install it as a Blender extension "
        "(blender.org/extensions) or as a legacy addon, or make sure it is enabled.")


def clear_scene() -> None:
    """Remove every object; keeps the file small and avoids cross-test pollution."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def import_pmx(filepath: str, scale: float = IMPORT_SCALE,
               rename_bones: bool = True) -> list[bpy.types.Object]:
    ensure_mmd_tools()
    before = set(bpy.data.objects)
    bpy.ops.mmd_tools.import_model(filepath=filepath, scale=scale,
                                  rename_bones=rename_bones,
                                  log_level='ERROR')
    return [o for o in bpy.data.objects if o not in before]


def mmd_root(obj: bpy.types.Object | None) -> bpy.types.Object | None:
    """The MMD root (an EMPTY with mmd_type == 'ROOT') an object belongs to."""
    while obj is not None:
        if getattr(obj, "mmd_type", "NONE") == "ROOT":
            return obj
        obj = obj.parent
    return None


def model_roots(objects: list[bpy.types.Object] | None = None) -> list[bpy.types.Object]:
    """Distinct MMD model roots among the given objects."""
    if objects is None:
        objects = list(bpy.data.objects)
    roots: list[bpy.types.Object] = []
    for o in objects:
        r = mmd_root(o)
        if r is not None and r not in roots:
            roots.append(r)
    return roots


def export_pmx(filepath: str, objects: list[bpy.types.Object] | None = None,
               scale: float = EXPORT_SCALE) -> str:
    """Export the MMD model to PMX.

    `mmd_tools.export_pmx` polls on `active_object` being an MMD root, so the
    root EMPTY has to be selected and active - not just any imported object.
    """
    ensure_mmd_tools()
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    if objects is None:
        objects = list(bpy.data.objects)
    roots = model_roots(objects)
    if not roots:
        raise RuntimeError("No MMD model root found among the given objects")
    # bpy.ops.object.select_all() fails in background mode on Blender 5.x
    # (no window context), so deselect through the view layer directly.
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for r in roots:
        r.select_set(True)
    bpy.context.view_layer.objects.active = roots[0]
    bpy.ops.mmd_tools.export_pmx(filepath=filepath, scale=scale,
                                 copy_textures_mode='SKIP_EXISTING',
                                 visible_meshes_only=False,
                                 log_level='ERROR')
    return filepath


def _texture_paths(materials: list[bpy.types.Material]) -> list[str]:
    out: list[str] = []
    for mat in materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == 'ShaderNodeTexImage' and node.image:
                p = node.image.filepath
                if p:
                    out.append(bpy.path.abspath(p))
    return sorted(set(out))


def model_meshes(objects: list[bpy.types.Object] | None = None) -> list[bpy.types.Object]:
    """Mesh objects that belong to the MMD model body (not rigid-body proxies).

    mmd_tools parents the body meshes under the armature and the collision
    proxies under a separate "rigidbodies" group, so walking up to the first
    ARMATURE ancestor separates the two cleanly.
    """
    if objects is None:
        objects = list(bpy.data.objects)
    out = []
    for o in objects:
        if o.type != 'MESH':
            continue
        p = o.parent
        while p is not None:
            if p.type == 'ARMATURE':
                out.append(o)
                break
            p = p.parent
    return out


def mesh_table(objects: list[bpy.types.Object] | None = None) -> list[dict[str, Any]]:
    """Per-mesh inventory: material slots, poly counts, local bounding box.

    PMX files often keep body and clothing inside one mesh, so the face ranges
    behind each material slot are the reliable handle. This table is what
    P1-01 works on.
    """
    if objects is None:
        objects = list(bpy.data.objects)
    out = []
    for o in sorted((x for x in objects if x.type == 'MESH'),
                    key=lambda x: x.name):
        me = o.data
        per_mat: dict[str, int] = {}
        for p in me.polygons:
            mi = p.material_index
            name = me.materials[mi].name if mi < len(me.materials) and me.materials[mi] else "<none>"
            per_mat[name] = per_mat.get(name, 0) + 1
        if me.vertices:
            xs = [v.co.x for v in me.vertices]
            ys = [v.co.y for v in me.vertices]
            zs = [v.co.z for v in me.vertices]
            bbox = [[round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)],
                    [round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)]]
        else:
            bbox = None
        out.append({
            "name": o.name,
            "vertices": len(me.vertices),
            "faces": len(me.polygons),
            "materials": [{"name": m.name if m else None,
                           "faces": per_mat.get(m.name if m else "<none>", 0)}
                          for m in me.materials],
            "bbox": bbox,
        })
    return out


def model_info(objects: list[bpy.types.Object] | None = None) -> dict[str, Any]:
    """The P1-00 inventory: objects, materials, meshes, bones, textures."""
    if objects is None:
        objects = list(bpy.data.objects)
    meshes = [o for o in objects if o.type == 'MESH']
    body = model_meshes(objects)
    arms = [o for o in objects if o.type == 'ARMATURE']
    mats = []
    seen = set()
    for o in body:
        for m in o.data.materials:
            if m and m.name not in seen:
                seen.add(m.name)
                mats.append(m)
    return {
        "objects": [{"name": o.name, "type": o.type,
                     "mmd_type": getattr(o, "mmd_type", "NONE"),
                     "parent": o.parent.name if o.parent else None}
                    for o in sorted(objects, key=lambda x: x.name)],
        "counts": {
            "objects": len(objects),
            "meshes": len(meshes),
            "body_meshes": len(body),
            "rigid_body_meshes": len(meshes) - len(body),
            "armatures": len(arms),
            "materials": len(mats),
            "vertices": sum(len(o.data.vertices) for o in body),
            "faces": sum(len(o.data.polygons) for o in body),
            "bones": sum(len(o.data.bones) for o in arms),
        },
        "materials": sorted(m.name for m in mats),
        "bones": {a.name: [b.name for b in a.data.bones] for a in arms},
        "bone_data": {a.name: bone_table(a) for a in arms},
        "textures": _texture_paths(mats),
        "parts": mesh_table(body),
    }


def bone_table(armature: bpy.types.Object) -> list[dict[str, Any]]:
    """bone name, parent, head/tail in armature space."""
    out = []
    for b in armature.data.bones:
        out.append({
            "name": b.name,
            "parent": b.parent.name if b.parent else None,
            "head": [round(v, 5) for v in b.head_local],
            "tail": [round(v, 5) for v in b.tail_local],
        })
    return out
