"""Clothing segmentation and preview (runs inside Blender).

PMX keeps the body and the clothes inside the same mesh, so a material slot
is only a coarse handle. The reliable unit is a *connected component of the
faces that share one material slot* - that is what this module produces.

Output per part:
  id, mesh, material, faces, vertices, bbox, center, category, confidence
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Vector

# --------------------------------------------------------------------------
# Name hints. MMD material names are Chinese / Japanese / English mix.
# --------------------------------------------------------------------------

# Strong clothing markers.
CLOTHING_WORDS = (
    "服", "衣", "裙", "裤", "襪", "袜", "袖", "鞋", "靴", "披", "袍", "装",
    "帯", "带", "巾", "裳", "铠", "甲", "领", "領", "纽", "扣", "饰", "飾",
    "飘", "飄", "ribbon", "skirt", "dress", "shirt", "cloth", "shoe",
    "sock", "coat", "pant", "sleeve", "belt", "uniform", "wear",
)
# Skin / flesh.
SKIN_WORDS = ("肌", "肤", "膚", "身", "体", "體", "肉", "乳", "腹", "肚",
              "skin", "body")
# Face features.
FACE_WORDS = ("面", "顔", "目", "眼", "眉", "睫", "口", "舌", "鼻", "cheek",
              "face", "eye", "brow", "lash", "mouth", "tongue")
# Hair and hair accessories.
HAIR_WORDS = ("髪", "发", "髮", "辫", "髻", "hair", "bang")
ACCESSORY_WORDS = ("饰", "飾", "飾品", "accessory", "ornament", "brooch",
                   "ribbon")

# --------------------------------------------------------------------------
# Part enumeration
# --------------------------------------------------------------------------


def _components(me: bpy.types.Mesh, face_ids: list[int]) -> list[dict[str, Any]]:
    """Split `face_ids` into connected components sharing an edge."""
    # edge -> first face seen with that edge
    edge_owner: dict[tuple[int, int], int] = {}
    parent: dict[int, int] = {f: f for f in face_ids}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for fid in face_ids:
        vs = me.polygons[fid].vertices
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            key = (a, b) if a < b else (b, a)
            if key in edge_owner:
                union(fid, edge_owner[key])
            else:
                edge_owner[key] = fid

    groups: dict[int, list[int]] = {}
    for fid in face_ids:
        groups.setdefault(find(fid), []).append(fid)

    out = []
    for faces in groups.values():
        vids = set()
        for fid in faces:
            vids.update(me.polygons[fid].vertices)
        out.append({"faces": faces, "verts": sorted(vids)})
    # biggest first, keeps part ids stable between runs
    out.sort(key=lambda c: -len(c["faces"]))
    return out


def enumerate_parts(meshes: list[bpy.types.Object]) -> list[dict[str, Any]]:
    """Every (material slot x connected component) of the body meshes."""
    parts: list[dict[str, Any]] = []
    pid = 0
    for ob in sorted(meshes, key=lambda o: o.name):
        me = ob.data
        for slot, mat in enumerate(me.materials):
            if mat is None:
                continue
            face_ids = [p.index for p in me.polygons if p.material_index == slot]
            if not face_ids:
                continue
            for comp in _components(me, face_ids):
                vids = comp["verts"]
                if not vids:
                    continue
                co = [me.vertices[i].co for i in vids]
                xs = [c.x for c in co]
                ys = [c.y for c in co]
                zs = [c.z for c in co]
                bbox_min = [min(xs), min(ys), min(zs)]
                bbox_max = [max(xs), max(ys), max(zs)]
                center = [(bbox_min[0] + bbox_max[0]) / 2,
                          (bbox_min[1] + bbox_max[1]) / 2,
                          (bbox_min[2] + bbox_max[2]) / 2]
                parts.append({
                    "id": pid,
                    "mesh": ob.name,
                    "material": mat.name,
                    "material_slot": slot,
                    "faces": comp["faces"],
                    "face_count": len(comp["faces"]),
                    "vertex_count": len(vids),
                    "bbox": [bbox_min, bbox_max],
                    "size": [bbox_max[i] - bbox_min[i] for i in range(3)],
                    "center": center,
                })
                pid += 1
    return parts


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def _hit(name: str, words: Iterable[str]) -> str | None:
    low = name.lower()
    for w in words:
        if w in low:
            return w
    return None


def _classify_material(name: str, faces: int, rel_z: float,
                       size: list[float], body_height: float) -> dict[str, Any]:
    """Classify one material slot. Explainable: name first, geometry second.

    Materials are the unit people actually pick, so the verdict is made per
    material - a MMD model regularly paints one material over dozens of
    separate islands (trim, lace, a whole outfit) and judging them one by one
    only produces noise.
    """
    reason: list[str] = []
    category = "unknown"
    confidence = 0.2

    hit = _hit(name, CLOTHING_WORDS)
    if hit:
        category, confidence = "clothing", 0.9
        reason.append(f"name contains clothing word {hit!r}")
    if hit is None:
        hit = _hit(name, ACCESSORY_WORDS)
        if hit:
            category, confidence = "accessory", 0.75
            reason.append(f"name contains accessory word {hit!r}")
    if category == "unknown":
        hit = _hit(name, SKIN_WORDS)
        if hit:
            category, confidence = "skin", 0.85
            reason.append(f"name contains skin word {hit!r}")
    if category == "unknown":
        hit = _hit(name, FACE_WORDS)
        if hit:
            category, confidence = "face", 0.85
            reason.append(f"name contains face word {hit!r}")
    if category == "unknown":
        hit = _hit(name, HAIR_WORDS)
        if hit:
            category, confidence = "hair", 0.8
            reason.append(f"name contains hair word {hit!r}")

    # Geometry fallback for unnamed materials ("新規", "new", "untitled"...).
    # A big shell sitting on the upper body is a cape / shoulder piece; the
    # face and the legs are excluded on purpose - they are the two places
    # where a wrong guess shows up immediately.
    if category == "unknown" and body_height > 0:
        if 0.55 <= rel_z <= 0.86 and faces >= 150:
            category, confidence = "clothing", 0.7
            reason.append("large unnamed shell in the upper-body band "
                          "(cape / shoulder region)")
        else:
            reason.append("no name hint and no convincing geometry hint")

    return {"category": category, "confidence": confidence,
            "reason": "; ".join(reason) if reason else "name hint"}


def classify_parts(parts: list[dict[str, Any]], body_height: float,
                   model_bbox: list[list[float]]) -> list[dict[str, Any]]:
    """Attach the material-level verdict to every part."""
    by_mat: dict[str, list[dict[str, Any]]] = {}
    for p in parts:
        by_mat.setdefault(p["material"], []).append(p)

    verdicts: dict[str, dict[str, Any]] = {}
    for name, ps in by_mat.items():
        faces = sum(x["face_count"] for x in ps)
        lo = [min(x["bbox"][0][i] for x in ps) for i in range(3)]
        hi = [max(x["bbox"][1][i] for x in ps) for i in range(3)]
        size = [hi[i] - lo[i] for i in range(3)]
        rel_z = ((lo[2] + hi[2]) / 2 - model_bbox[0][2]) / max(body_height, 1e-6)
        verdicts[name] = _classify_material(name, faces, rel_z, size, body_height)

    out = []
    for p in parts:
        q = dict(p)
        v = verdicts[p["material"]]
        q["category"] = v["category"]
        q["confidence"] = v["confidence"]
        q["reason"] = v["reason"]
        q["relative_height"] = (
            (p["center"][2] - model_bbox[0][2]) / body_height
            if body_height > 0 else 0.0)
        out.append(q)
    return out


def material_table(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Roll the parts up per material slot - the level people actually pick.

    A single MMD material often covers dozens of separate islands (trim strips,
    lace, pattern overlays), so the connected-component list is too fine to
    choose from by hand while the material list is exactly the right size.
    """
    by_mat: dict[str, list[dict[str, Any]]] = {}
    for p in parts:
        by_mat.setdefault(p["material"], []).append(p)
    out = []
    for name, ps in by_mat.items():
        cat_faces: dict[str, int] = {}
        for x in ps:
            cat_faces[x["category"]] = cat_faces.get(x["category"], 0) + x["face_count"]
        category = max(cat_faces, key=cat_faces.get)
        conf = max((x["confidence"] for x in ps if x["category"] == category),
                   default=0.0)
        lo = [min(x["bbox"][0][i] for x in ps) for i in range(3)]
        hi = [max(x["bbox"][1][i] for x in ps) for i in range(3)]
        out.append({
            "material": name,
            "part_count": len(ps),
            "face_count": sum(x["face_count"] for x in ps),
            "vertex_count": sum(x["vertex_count"] for x in ps),
            "category": category,
            "confidence": conf,
            "reason": next(x["reason"] for x in ps if x["category"] == category),
            "bbox": [lo, hi],
            "center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)],
            "part_ids": [x["id"] for x in ps],
        })
    out.sort(key=lambda m: -m["face_count"])
    return out


def suggest_selection(parts: list[dict[str, Any]],
                      materials: list[dict[str, Any]]) -> dict[str, Any]:
    """Default choice: high-confidence clothing + accessories, no skin/face/hair."""
    keep = {m["material"] for m in materials
            if m["category"] in ("clothing", "accessory") and m["confidence"] >= 0.7}
    chosen = [p["id"] for p in parts if p["material"] in keep]
    skipped = [{"material": m["material"], "category": m["category"],
                "confidence": m["confidence"], "face_count": m["face_count"],
                "part_count": m["part_count"]}
               for m in materials if m["material"] not in keep]
    return {
        "selected_parts": chosen,
        "selected_materials": sorted(keep),
        "skipped": skipped,
        "note": ("edit selected_parts / selected_materials if the automatic "
                 "choice misses or over-selects a part"),
    }


# --------------------------------------------------------------------------
# Preview rendering
# --------------------------------------------------------------------------

VIEW_DIRS = {
    "front": (0.0, -1.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
}


def _palette(n: int) -> list[tuple[float, float, float]]:
    """Distinct, readable colours for part ids."""
    out = []
    for i in range(n):
        h = (i * 0.618033988749895) % 1.0
        import colorsys
        r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.95)
        out.append((r, g, b))
    return out


def _scene_bbox(objs: list[bpy.types.Object]) -> list[list[float]]:
    lo = [1e9, 1e9, 1e9]
    hi = [-1e9, -1e9, -1e9]
    for o in objs:
        if o.type != 'MESH':
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
    return [lo, hi]


def _make_camera(scene, bbox, view: str, ortho_scale: float):
    from mathutils import Vector
    center = Vector([(bbox[0][i] + bbox[1][i]) / 2 for i in range(3)])
    d = Vector(VIEW_DIRS[view])
    size = max(bbox[1][i] - bbox[0][i] for i in range(3))
    cam_data = bpy.data.cameras.new(f"PreviewCam_{view}")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = ortho_scale
    cam = bpy.data.objects.new(f"PreviewCam_{view}", cam_data)
    scene.collection.objects.link(cam)
    cam.location = center + d * (size * 3 + 1.0)
    # point at the centre
    direction = (center - cam.location).normalized()
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def _preview_material(name: str = "PartPreviewMat") -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.7
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    try:
        attr = nt.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = "PartCol"
        color_socket = attr.outputs["Color"]
    except RuntimeError:
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "PartCol"
        color_socket = attr.outputs["Color"]
    nt.links.new(color_socket, bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _duplicate_with_colors(meshes, parts, color_of_part, name_suffix="_pmap"):
    """Copy the body meshes and paint every part in one flat colour."""
    copies = []

    mat = _preview_material()
    for ob in meshes:
        new = ob.copy()
        new.data = ob.data.copy()
        new.name = ob.name + name_suffix
        bpy.context.scene.collection.objects.link(new)
        me = new.data
        me.materials.clear()
        me.materials.append(mat)
        for p in me.polygons:
            p.material_index = 0
        # colour attribute on corners so faces of different parts never blend
        try:
            attr = me.color_attributes.new(name="PartCol", type='BYTE_COLOR',
                                          domain='CORNER')
        except Exception:
            attr = me.color_attributes.get("PartCol")
        # map face -> part id
        face_part: dict[tuple[str, int], int] = {}
        for p in parts:
            if p["mesh"] != ob.name:
                continue
            for fid in p["faces"]:
                face_part[(ob.name, fid)] = p["id"]
        for poly in me.polygons:
            col = (0.35, 0.35, 0.38, 1.0)
            pid = face_part.get((ob.name, poly.index))
            if pid is not None:
                c = color_of_part(pid)
                col = (c[0], c[1], c[2], 1.0)
            for li in poly.loop_indices:
                attr.data[li].color = col
        copies.append(new)
    return copies


def _setup_lights(scene):
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
        bg.inputs[1].default_value = 1.0
    scene.world = world
    for name, loc, energy in (("Key", (2.0, -3.0, 3.0), 260.0),
                              ("Fill", (-3.0, -2.0, 1.0), 110.0),
                              ("Rim", (0.0, 3.5, 2.5), 170.0)):
        ld = bpy.data.lights.new(f"PreviewLight_{name}", type='AREA')
        ld.energy = energy
        ld.size = 3.0
        lo = bpy.data.objects.new(f"PreviewLight_{name}", ld)
        lo.location = loc
        scene.collection.objects.link(lo)
        # aim at the origin-ish by rotating manually
        from mathutils import Vector
        direction = (Vector((0, 0, 1.0)) - Vector(loc)).normalized()
        lo.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


# Category colours: clothing must be the most obvious thing in the picture.
CATEGORY_COLORS = {
    "clothing": (0.20, 0.80, 0.35),
    "accessory": (0.95, 0.55, 0.15),
    "skin": (0.95, 0.75, 0.65),
    "face": (0.25, 0.55, 0.95),
    "hair": (0.70, 0.35, 0.85),
    "unknown": (0.45, 0.45, 0.50),
}


def _material_colors(parts: list[dict[str, Any]]) -> dict[int, tuple]:
    names = sorted({p["material"] for p in parts})
    pal = _palette(len(names))
    return {p["id"]: pal[names.index(p["material"])]
            for p in parts}


def _category_colors(parts: list[dict[str, Any]]) -> dict[int, tuple]:
    return {p["id"]: CATEGORY_COLORS.get(p["category"], CATEGORY_COLORS["unknown"])
            for p in parts}


def _selection_colors(parts: list[dict[str, Any]],
                      selected: set[int]) -> dict[int, tuple]:
    return {p["id"]: ((0.15, 0.85, 0.40) if p["id"] in selected
                      else (0.42, 0.42, 0.46))
            for p in parts}


def _render_views(scene, meshes, copies, bbox, ortho, out_dir, prefix):
    written = []
    for view in VIEW_DIRS:
        cam = _make_camera(scene, bbox, view, ortho)
        scene.render.filepath = str(out_dir / f"{prefix}_{view}.png")
        bpy.ops.render.render(write_still=True)
        written.append(scene.render.filepath)
        bpy.data.objects.remove(cam, do_unlink=True)
    return written


def render_preview(meshes, parts, out_dir, width=900, height=1200,
                   selected: set[int] | None = None) -> list[str]:
    """Render 4 orthographic views for every colour scheme plus a textured pass.

    Schemes:
      partmap_material  - one colour per material slot
      partmap_category  - one colour per classification (clothing / skin / ...)
      partmap_selection - the currently selected clothing parts highlighted
      textured          - the original MMD materials, for reference
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    try:
        scene.view_settings.view_transform = 'Standard'
    except Exception:
        pass

    bbox = _scene_bbox(meshes)
    size = max(bbox[1][i] - bbox[0][i] for i in range(3))
    ortho = size * 1.12
    _setup_lights(scene)

    schemes = [
        ("partmap_material", _material_colors(parts)),
        ("partmap_category", _category_colors(parts)),
        ("partmap_selection", _selection_colors(parts, selected or set())),
    ]

    written = []
    for prefix, color_map in schemes:
        copies = _duplicate_with_colors(meshes, parts, color_map.get)
        for ob in meshes:
            ob.hide_render = True
        written += _render_views(scene, meshes, copies, bbox, ortho, out_dir,
                                 prefix)
        for c in copies:
            bpy.data.objects.remove(c, do_unlink=True)
        for ob in meshes:
            ob.hide_render = False

    written += _render_views(scene, meshes, [], bbox, ortho, out_dir, "textured")
    return written


# --------------------------------------------------------------------------
# Entry point used by the runner
# --------------------------------------------------------------------------


def extract_preview(objects: list[bpy.types.Object], out_dir: str) -> dict[str, Any]:
    from . import import_export as ie

    meshes = ie.model_meshes(objects)
    if not meshes:
        raise RuntimeError("no body mesh found in the imported model")

    parts = enumerate_parts(meshes)
    bbox = _scene_bbox(meshes)
    body_height = bbox[1][2] - bbox[0][2]
    classified = classify_parts(parts, body_height, bbox)
    materials = material_table(classified)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "body_meshes": [o.name for o in meshes],
        "model_bbox": bbox,
        "body_height": body_height,
        "materials": materials,
        "parts": classified,
    }
    (out / "parts.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    selection = suggest_selection(classified, materials)
    (out / "selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=1), encoding="utf-8")

    selected_ids = set(selection["selected_parts"])
    images = render_preview(meshes, classified, out / "preview",
                            selected=selected_ids)

    return {
        "out_dir": str(out),
        "parts": [{"id": p["id"], "material": p["material"],
                   "category": p["category"], "confidence": p["confidence"],
                   "face_count": p["face_count"],
                   "vertex_count": p["vertex_count"],
                   "center": [round(v, 4) for v in p["center"]]}
                  for p in classified],
        "materials": materials,
        "selection": selection,
        "images": images,
        "parts_json": str(out / "parts.json"),
        "selection_json": str(out / "selection.json"),
    }
