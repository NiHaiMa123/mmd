"""Retarget an extracted garment onto the fixed base body.

P1-03 .. P1-06 of the plan. The core idea:

  * A bone mapping turns the source rig into the target rig (MMD models share
    the standard bone names, so the mapping is mostly identity).
  * Every matched bone gets a *rest delta*  D = M_target @ M_source^-1  which
    maps the source bone frame onto the target bone frame. Re-skinning the
    garment with a weighted blend of those deltas carries the garment over
    while keeping the seams smooth - and because the deltas are per bone, the
    different body proportions of the two models are handled for free.
  * Garment-only bones (skirt / sleeve / ribbon chains) are re-created in the
    target armature at the transformed position, so the outfit keeps its own
    rig instead of being glued to the legs.
  * Tight regions (driven by body bones) get pulled onto the target body;
    loose regions (driven by garment bones) keep their silhouette.
  * The body that the garment covers is measured on the SOURCE model and the
    coverage is transferred to the target, so openings (collar, cuffs, hem)
    keep the skin they should keep.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

_CONTAIN_DIRS = (
    Vector((0.0, 0.0, 1.0)), Vector((0.0, 0.0, -1.0)),
    Vector((1.0, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)),
    Vector((0.0, 1.0, 0.0)), Vector((0.0, -1.0, 0.0)),
)



# Materials that are never "body skin" for the fit / mask step.
HAIR_WORDS = ("髪", "发", "髮", "辫", "髻", "hair", "bang")
FACE_WORDS = ("面", "顔", "目", "眼", "眉", "睫", "口", "舌", "鼻",
              "face", "eye", "brow", "lash", "mouth", "tongue")


# --------------------------------------------------------------------------
# Rig map
# --------------------------------------------------------------------------


def build_rig_map(src_arm: bpy.types.Object, tgt_arm: bpy.types.Object,
                  used_bones: set[str]) -> dict[str, Any]:
    """Map source bones to target bones.

    MMD models share the standard bone names, so the mapping is the identity
    for every body bone. Source bones the target does not have are either
    garment helpers (kept, re-created) or face/hair helpers (dropped).
    """
    tgt_names = {b.name for b in tgt_arm.data.bones}
    src_names = [b.name for b in src_arm.data.bones]

    mapping = {n: n for n in src_names if n in tgt_names}
    garment = [n for n in src_names if n not in tgt_names]
    dropped = [n for n in garment if n not in used_bones]
    keep = [n for n in garment if n in used_bones]

    return {
        "mapping": mapping,
        "garment_bones": keep,
        "dropped_bones": dropped,
        "target_only_bones": sorted(tgt_names - set(src_names)),
        "mapped_body_bones": sorted(n for n in mapping if n in used_bones),
    }


def rest_deltas(src_arm: bpy.types.Object, tgt_arm: bpy.types.Object,
                mapping: dict[str, str]) -> dict[str, Matrix]:
    """D = the transform that carries a source bone frame onto a target one.

    The obvious choice - ``M_target @ M_source^-1`` - is wrong: the roll of a
    bone is an arbitrary authoring decision, and the two models do not agree
    on it.  Inheriting that difference rotates the garment around the bone
    axis and throws the part far away (a wrist ended up 1.3 m off).

    So only two things are mapped: where the bone starts and which way it
    points.  The rotation is the minimal one that aligns the two directions,
    taken around the bone's own origin:

        D(p) = R(p - head_source) + head_target

    The roll difference is dropped, the anatomical difference is kept.
    """
    S = {b.name: b for b in src_arm.data.bones}
    T = {b.name: b for b in tgt_arm.data.bones}
    out = {}
    for s, t in mapping.items():
        if s not in S or t not in T:
            continue
        sb, tb = S[s], T[t]
        d_s = sb.tail_local - sb.head_local
        d_t = tb.tail_local - tb.head_local
        if d_s.length < 1e-9 or d_t.length < 1e-9:
            out[s] = Matrix.Translation(tb.head_local - sb.head_local)
            continue
        d_s.normalize()
        d_t.normalize()
        rot = d_s.rotation_difference(d_t).to_matrix().to_4x4()
        out[s] = (Matrix.Translation(tb.head_local)
                  @ rot
                  @ Matrix.Translation(-sb.head_local))
    return out


def _bone_depth(src_arm: bpy.types.Object, name: str) -> int:
    depth = 0
    bone = src_arm.data.bones.get(name)
    while bone is not None and bone.parent is not None:
        depth += 1
        bone = bone.parent
    return depth


def garment_deltas(src_arm: bpy.types.Object, garment_bones: list[str],
                   body_deltas: dict[str, Matrix]) -> dict[str, Matrix]:
    """Delta for every garment-only bone (skirt / sleeve / ribbon chains).

    A garment bone rides on its parent, so its new position follows the
    parent's transform; its own direction is carried over unchanged, which
    keeps the chain's shape.  The delta therefore maps the source bone frame
    onto the new one exactly like the body bones do - with the parent's
    delta alone every bone of a chain would collapse into one transform and
    the skirt could not swing.
    """
    S = {b.name: b for b in src_arm.data.bones}
    out: dict[str, Matrix] = {}

    def parent_delta(name: str) -> Matrix:
        if name in body_deltas:
            return body_deltas[name]
        if name in out:
            return out[name]
        bone = S.get(name)
        if bone is None or bone.parent is None:
            return Matrix.Identity(4)
        return parent_delta(bone.parent.name)

    for name in sorted(garment_bones, key=lambda n: _bone_depth(src_arm, n)):
        bone = S.get(name)
        if bone is None or bone.parent is None:
            continue
        pd = parent_delta(bone.parent.name)
        head_s = bone.head_local
        head_t = pd @ head_s
        d_s = bone.tail_local - bone.head_local
        d_t = pd.to_3x3() @ d_s
        if d_s.length > 1e-9 and d_t.length > 1e-9:
            rot = d_s.normalized().rotation_difference(
                d_t.normalized()).to_matrix().to_4x4()
            out[name] = (Matrix.Translation(head_t)
                         @ rot
                         @ Matrix.Translation(-head_s))
        else:
            out[name] = Matrix.Translation(head_t - head_s)
    return out


def garment_bone_specs(src_arm: bpy.types.Object, garment_bones: list[str],
                       deltas: dict[str, Matrix]) -> list[dict[str, Any]]:
    """Head / tail / parent / roll direction for every garment-only bone."""
    S = {b.name: b for b in src_arm.data.bones}
    specs = []
    for name in garment_bones:
        bone = S.get(name)
        if bone is None:
            continue
        parent = bone.parent.name if bone.parent else None
        d = deltas.get(name)
        if d is None or parent is None:
            continue
        head = d @ bone.head_local
        tail = d @ bone.tail_local
        specs.append({
            "name": name,
            "parent": parent,
            "head": head,
            "tail": tail,
            "roll_axis": (d.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized(),
        })
    # parents must exist before their children
    specs.sort(key=lambda s: (s["parent"] in {x["name"] for x in specs}, s["name"]))
    return specs


def add_bones(tgt_arm: bpy.types.Object, specs: list[dict[str, Any]]) -> list[str]:
    """Create the garment bones inside the target armature."""
    if not specs:
        return []
    view_layer = bpy.context.view_layer
    for o in view_layer.objects:
        o.select_set(False)
    tgt_arm.select_set(True)
    view_layer.objects.active = tgt_arm
    bpy.ops.object.mode_set(mode='EDIT')

    created: dict[str, Any] = {}
    try:
        for spec in specs:
            eb = tgt_arm.data.edit_bones.new(spec["name"])
            eb.head = spec["head"]
            eb.tail = spec["tail"]
            eb.roll = 0.0
            try:
                eb.align_roll(spec["roll_axis"])
            except Exception:
                pass
            created[spec["name"]] = eb
        for spec in specs:
            eb = created[spec["name"]]
            parent = created.get(spec["parent"])
            if parent is None:
                parent = tgt_arm.data.edit_bones.get(spec["parent"])
            if parent is not None:
                eb.parent = parent
                eb.use_connect = False
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    return [s["name"] for s in specs]


# --------------------------------------------------------------------------
# Re-skin
# --------------------------------------------------------------------------


def apply_positions(me: bpy.types.Mesh, new_positions) -> None:
    """Set the vertex positions and move every shape key by the same delta.

    Blender keeps the shape key data in its own array, separate from
    ``mesh.vertices``.  Editing the vertices alone therefore leaves the morphs
    - and, more importantly, the *evaluated* mesh that the renderer and the
    PMX exporter actually use - at the old place.  The whole retarget would
    silently do nothing.

    Moving the shape keys by the same delta keeps the morph effect: the
    difference between a morph and the basis is unchanged.
    """
    old = [v.co.copy() for v in me.vertices]
    if len(old) != len(new_positions):
        raise ValueError("position count does not match the vertex count")
    delta = [n - o for n, o in zip(new_positions, old)]
    for v, n in zip(me.vertices, new_positions):
        v.co = n
    if not me.shape_keys:
        return
    moved = False
    for key in me.shape_keys.key_blocks:
        buf = [0.0] * (len(me.vertices) * 3)
        key.data.foreach_get("co", buf)
        for i, d in enumerate(delta):
            if d.length_squared == 0.0:
                continue
            moved = True
            buf[3 * i] += d.x
            buf[3 * i + 1] += d.y
            buf[3 * i + 2] += d.z
        key.data.foreach_set("co", buf)
    me.update()


def reskin(garment: bpy.types.Object, deltas: dict[str, Matrix],
           bone_map: dict[str, str]) -> dict[str, Any]:
    """Move the garment into the target rig and rename the vertex groups.

    The new position of a vertex is the linear blend of the per-bone rest
    deltas, weighted exactly like the skinning weights - that keeps the
    surface continuous across bone borders.
    """
    me = garment.data
    src_names = [vg.name for vg in garment.vertex_groups]
    remap = {g.index: bone_map.get(src_names[g.index], src_names[g.index])
             for g in garment.vertex_groups}

    weighted = [0.0] * len(me.vertices)
    zero3 = Matrix.Identity(3) * 0.0
    new_positions = []
    for v in me.vertices:
        rot = zero3.copy()
        trans = Vector((0.0, 0.0, 0.0))
        wsum = 0.0
        for g in v.groups:
            name = src_names[g.group]
            d = deltas.get(name)
            if d is None or g.weight <= 0.0:
                continue
            rot = rot + d.to_3x3() * g.weight
            trans = trans + d.to_translation() * g.weight
            wsum += g.weight
        if wsum > 0.0:
            if abs(wsum - 1.0) > 1e-4:
                # PMX weights are normalised on import, but never trust it
                new_positions.append((rot @ v.co + trans) / wsum)
            else:
                new_positions.append(rot @ v.co + trans)
            weighted[v.index] = wsum
        else:
            new_positions.append(v.co.copy())
    apply_positions(me, new_positions)

    # rebuild the groups under the mapped names
    new_groups: dict[str, list[tuple[int, float]]] = {}
    for v in me.vertices:
        for g in v.groups:
            if g.weight <= 0.0:
                continue
            name = remap[g.group]
            new_groups.setdefault(name, []).append((v.index, g.weight))

    old_groups = list(garment.vertex_groups)
    for vg in old_groups:
        garment.vertex_groups.remove(vg)
    for name, items in new_groups.items():
        vg = garment.vertex_groups.new(name=name)
        by_weight: dict[float, list[int]] = {}
        for index, weight in items:
            by_weight.setdefault(round(weight, 6), []).append(index)
        for weight, indices in by_weight.items():
            vg.add(indices, weight, 'REPLACE')

    return {"vertices_moved": sum(1 for w in weighted if w > 0.0),
            "groups": len(new_groups)}


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------


def _material_is(obj: bpy.types.Object, index: int, words) -> bool:
    me = obj.data
    if index >= len(me.materials) or me.materials[index] is None:
        return False
    name = me.materials[index].name.lower()
    return any(w in name for w in words)


def body_faces(obj: bpy.types.Object, skip_hair=True,
               skip_face=True) -> list[int]:
    """Face indices of a mesh that count as body (not hair, not face parts)."""
    me = obj.data
    out = []
    for p in me.polygons:
        if skip_hair and _material_is(obj, p.material_index, HAIR_WORDS):
            continue
        if skip_face and _material_is(obj, p.material_index, FACE_WORDS):
            continue
        out.append(p.index)
    return out


def build_bvh(obj: bpy.types.Object, face_indices: list[int] | None = None
              ) -> BVHTree:
    me = obj.data
    mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    if face_indices is None:
        polys = [list(p.vertices) for p in me.polygons]
    else:
        polys = [list(me.polygons[i].vertices) for i in face_indices]
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


# --------------------------------------------------------------------------
# Fit: tight regions hug the target body, loose regions keep their shape
# --------------------------------------------------------------------------


def _barycentric(co: Vector, a: Vector, b: Vector, c: Vector):
    """Barycentric weights of `co` inside the triangle abc."""
    v0 = c - a
    v1 = b - a
    v2 = co - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return 1.0, 0.0, 0.0
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    return 1.0 - v - w, v, w


def _vertex_weights(mesh_obj: bpy.types.Object, index: int) -> dict[str, float]:
    """The skin weights of one vertex, keyed by bone name."""
    names = [vg.name for vg in mesh_obj.vertex_groups]
    out: dict[str, float] = {}
    for g in mesh_obj.data.vertices[index].groups:
        if g.weight <= 0.0:
            continue
        name = names[g.group]
        if name.startswith(("mmd_", "UV_", "_")):
            continue
        out[name] = out.get(name, 0.0) + g.weight
    return out


def transfer_target_weights(garment: bpy.types.Object, target_body: bpy.types.Object,
                            body_bones: set[str], tightness: list[float],
                            blend: float = 0.8, max_dist: float = 0.06
                            ) -> dict[str, Any]:
    """Give the tight parts of the garment the target body's weight gradient.

    The plan asks for the skin weights to be taken from the base body by
    nearest face interpolation - that is what makes a garment follow the
    shoulders, armpit and hips of *this* body instead of the proportions of
    the body the garment was modelled on.  The loose parts (skirt, sleeves)
    keep their own garment bones.
    """
    from . import import_export as ie

    me = garment.data
    tme = target_body.data
    tmw = target_body.matrix_world
    skin_faces = body_faces(target_body, skip_hair=True, skip_face=True)
    bvh = build_bvh(target_body, skin_faces)

    gnames = [vg.name for vg in garment.vertex_groups]
    # current weights per vertex
    current: list[dict[str, float]] = []
    for v in me.vertices:
        d: dict[str, float] = {}
        for g in v.groups:
            if g.weight <= 0.0:
                continue
            d[gnames[g.group]] = d.get(gnames[g.group], 0.0) + g.weight
        current.append(d)

    updated = 0
    for vi, v in enumerate(me.vertices):
        t = tightness[vi] * blend
        if t <= 0.001:
            continue
        loc, _nrm, fi, dist = bvh.find_nearest(v.co)
        if loc is None or dist > max_dist:
            continue
        poly = tme.polygons[fi]
        if len(poly.vertices) != 3:
            continue
        a, b, c = [tmw @ tme.vertices[i].co for i in poly.vertices]
        w0, w1, w2 = _barycentric(loc, a, b, c)
        blended: dict[str, float] = {}
        for i, bw in zip(poly.vertices, (w0, w1, w2)):
            if bw <= 0.0:
                continue
            for name, weight in _vertex_weights(target_body, i).items():
                blended[name] = blended.get(name, 0.0) + bw * weight
        if not blended:
            continue
        new: dict[str, float] = {}
        for name, weight in current[vi].items():
            if name in body_bones:
                new[name] = t * blended.get(name, 0.0) + (1.0 - t) * weight
            else:
                new[name] = (1.0 - t) * weight
        for name, weight in blended.items():
            if name in body_bones:
                new[name] = new.get(name, 0.0) + t * weight
        # keep the sum at one
        total = sum(new.values())
        if total > 1e-6:
            for name in list(new):
                new[name] /= total
        current[vi] = new
        updated += 1

    # write the weights back
    for vg in list(garment.vertex_groups):
        garment.vertex_groups.remove(vg)
    buckets: dict[str, dict[float, list[int]]] = {}
    for vi, weights in enumerate(current):
        for name, weight in weights.items():
            if weight <= 0.0:
                continue
            buckets.setdefault(name, {}).setdefault(round(weight, 6),
                                                    []).append(vi)
    for name, by_weight in buckets.items():
        vg = garment.vertex_groups.new(name=name)
        for weight, indices in by_weight.items():
            vg.add(indices, weight, 'REPLACE')

    return {"vertices_reweighted": updated,
            "groups": len(buckets)}


# --------------------------------------------------------------------------
# Limb end fitting: the finger sleeves and the shoes
# --------------------------------------------------------------------------

# The outfit was modelled on a smaller hand and foot than the base body has,
# so the fingers push through the finger sleeves and the foot bulges out of
# the shoe.  These are the bones that describe the limb and the clearance
# the outfit keeps around it.
LIMB_ENDS = {
    "hand_l": ("手首.L", "小指３.L", 0.004),
    "hand_r": ("手首.R", "小指３.R", 0.004),
    "foot_l": ("足首.L", "つま先.L", 0.006),
    "foot_r": ("足首.R", "つま先.R", 0.006),
}


def _limb_axis(armature: bpy.types.Object, root: str, tip: str):
    """The axis of a limb: from the root bone to the tip of the last bone."""
    rb = armature.data.bones.get(root)
    tb = armature.data.bones.get(tip)
    if rb is None or tb is None:
        return None
    head = armature.matrix_world @ rb.head_local
    tail = armature.matrix_world @ tb.tail_local
    direction = tail - head
    if direction.length < 1e-6:
        return None
    return head, direction.normalized(), (tail - head).length


def fit_limb_ends(garment: bpy.types.Object, target_body: bpy.types.Object,
                  tgt_arm: bpy.types.Object, body_bvh: BVHTree,
                  max_reach: float = 0.14) -> dict[str, Any]:
    """Fit the finger sleeves and the shoes onto the base body's limbs.

    Every vertex of those parts is placed on the base body surface plus a
    small clearance, measured radially around the limb axis.  The outfit
    keeps its shape along the limb - a sleeve is not stretched into a
    different shape - it only gets the thickness the bigger hand needs.
    """
    me = garment.data
    stats: dict[str, Any] = {"moved": 0, "regions": {}}

    for name, (root, tip, clearance) in LIMB_ENDS.items():
        axis = _limb_axis(tgt_arm, root, tip)
        if axis is None:
            continue
        head, direction, length = axis
        # the part of the garment that belongs to this limb
        reach = max_reach
        moved = 0
        new_positions = []
        for v in me.vertices:
            co = v.co
            rel = co - head
            along = rel.dot(direction)
            if along < -0.03 or along > length + 0.10:
                new_positions.append(co)
                continue
            radial = rel - direction * along
            r = radial.length
            if r < 1e-5 or r > reach:
                new_positions.append(co)
                continue
            rd = radial / r
            loc, _n, _i, _d = body_bvh.ray_cast(head + direction * along, rd,
                                                reach)
            if loc is None:
                new_positions.append(co)
                continue
            new_positions.append(loc + rd * clearance)
            moved += 1
        apply_positions(me, new_positions)
        stats["regions"][name] = moved
        stats["moved"] += moved

    return stats


# --------------------------------------------------------------------------
# Hand and foot: lay the glove and the shoe back onto the base body
# --------------------------------------------------------------------------

# 刻晴's glove and shoe are not shells that sit around her fingers and toes:
# they *are* her finger and toe surfaces, painted with the outfit material
# (the measurement says so - every garment vertex of the hand and foot region
# lies exactly on the source body, and the face counts show the material is
# doubled on the same vertices, so there is no thickness to preserve).
#
# 达妮娅's fingers are about 1.4x thicker and her toes reach further, so
# after the retarget the whole glove is buried inside her hand and her toes
# stick out in front of the shoe.  The only correct fix is to put the glove and
# the shoe back onto the base body's own hand and foot surface - the same
# relative coverage the outfit had on its own body.

HAND_BONE_NAMES = frozenset({
    "手首", "手捩", "手捩1", "手捩2",
    "親指０", "親指１", "親指２",
    "人指１", "人指２", "人指３",
    "中指１", "中指２", "中指３",
    "薬指１", "薬指２", "薬指３",
    "小指１", "小指２", "小指３",
})

FOOT_BONE_NAMES = frozenset({
    "足首", "足首D", "足D", "足D++", "足先EX", "つま先", "足先",
    "足親指０", "足親指１",
    "足人指１", "足人指２", "足中指１", "足中指２",
    "足薬指１", "足薬指２", "足小指１", "足小指２",
})


def _bone_base(name: str) -> str:
    """'人指１.L' -> '人指１'."""
    if "." in name:
        return name.rpartition(".")[0]
    if name.endswith("_L") or name.endswith("_R"):
        return name[:-2]
    return name


def _bone_side(name: str) -> str:
    """'人指１.L' -> 'L', '' when the bone carries no side."""
    if "." in name:
        side = name.rpartition(".")[2]
        return side if side in ("L", "R") else ""
    if name.endswith("_L"):
        return "L"
    if name.endswith("_R"):
        return "R"
    return ""


def limb_region(name: str) -> str | None:
    """'hand' / 'foot' for a bone name, None when the bone is neither."""
    base = _bone_base(name)
    if base in HAND_BONE_NAMES:
        return "hand"
    if base in FOOT_BONE_NAMES:
        return "foot"
    return None


AUX_GROUPS = ("mmd_", "UV_", "_")


def dominant_bones(mesh_obj: bpy.types.Object) -> list[str]:
    """The bone that drives each vertex.

    The mmd_tools helper groups have to be left out: `mmd_edge_scale` sits on
    every vertex with a weight of 1.0, so a plain "largest weight wins" would
    call every vertex an edge scale and never find a bone at all.
    """
    groups = [vg.name for vg in mesh_obj.vertex_groups]
    out = []
    for v in mesh_obj.data.vertices:
        best, bw = "", 0.0
        for g in v.groups:
            name = groups[g.group]
            if name.startswith(AUX_GROUPS):
                continue
            if g.weight > bw:
                best, bw = name, g.weight
        out.append(best)
    return out


def limb_regions(mesh_obj: bpy.types.Object) -> list[str | None]:
    """'hand_L' / 'foot_R' for every vertex, None where the limb is unknown."""
    out = []
    for name in dominant_bones(mesh_obj):
        region = limb_region(name)
        side = _bone_side(name) if region else ""
        out.append(f"{region}_{side}" if region and side else None)
    return out


def _vertex_limb(mesh_obj: bpy.types.Object, min_weight: float) -> list[str | None]:
    """The hand / foot a body vertex belongs to, by the bones that drive it."""
    names = [vg.name for vg in mesh_obj.vertex_groups]
    out: list[str | None] = []
    for v in mesh_obj.data.vertices:
        key = None
        for g in v.groups:
            name = names[g.group]
            if name.startswith(AUX_GROUPS) or g.weight < min_weight:
                continue
            region = limb_region(name)
            side = _bone_side(name) if region else ""
            if region and side:
                key = f"{region}_{side}"
                break
        out.append(key)
    return out


def limb_bvhs(body_meshes: list[bpy.types.Object],
              min_weight: float = 0.3) -> dict[str, BVHTree]:
    """One BVH per hand and foot, from the body faces the limb bones drive.

    The whole body cannot be searched: in an A-pose the hands hang right next
    to the skirt, so the nearest surface to a finger is often a fold of the
    skirt.  Each limb therefore gets its own tree, and only the body parts the
    hand and foot bones actually drive end up in it.
    """
    verts: list = []
    polys: dict[str, list[list[int]]] = {}
    for obj in body_meshes:
        me = obj.data
        mw = obj.matrix_world
        base = len(verts)
        verts.extend([mw @ v.co for v in me.vertices])
        keys = _vertex_limb(obj, min_weight)
        for p in me.polygons:
            found = {keys[i] for i in p.vertices}
            if len(found) != 1:
                continue
            key = found.pop()
            if key is None:
                continue
            polys.setdefault(key, []).append([i + base for i in p.vertices])
    return {key: BVHTree.FromPolygons(verts, faces, all_triangles=False,
                                       epsilon=0.0)
            for key, faces in polys.items()}


def fit_limb_regions(garment: bpy.types.Object, tgt_bvhs: dict[str, BVHTree],
                     margin: float = 0.003, max_dist: float = 0.05,
                     near_dist: float = 0.004, rounds: int = 4,
                     max_push: float = 0.012) -> dict[str, Any]:
    """Lay the glove and the shoe back onto the base body's hand and foot.

    A vertex that ended up *inside* the base body - or within a few
    millimetres of it - is moved onto the surface plus a small margin, so the
    glove ends up around the base body's fingers instead of buried in them.
    Everything that sits away from the body (the heel of a shoe, the frill of a
    cuff) keeps its shape.

    The base body is modelled in far more detail than the outfit, so a face of
    the outfit that is laid on the surface still chords across a finger web or
    the arch of a foot and dips back into the skin.  Those faces are measured
    and the outfit is inflated around them.  The inflation is a *vector* field
    that is smoothed over the mesh, so the glove bulges like a real glove
    instead of tearing into spikes.
    """
    me = garment.data
    regions = limb_regions(garment)
    positions = []
    stats: dict[str, Any] = {"moved": 0, "regions": {}}
    for i, v in enumerate(me.vertices):
        key = regions[i]
        bvh = tgt_bvhs.get(key) if key else None
        if bvh is None:
            positions.append(v.co)
            continue
        loc, nrm, _idx, dist = bvh.find_nearest(v.co)
        if loc is None or nrm.length < 1e-6 or dist > max_dist:
            positions.append(v.co)
            continue
        # outside the surface and not touching it -> the piece is fine
        if (v.co - loc).dot(nrm) >= 0.0 and dist > near_dist:
            positions.append(v.co)
            continue
        positions.append(loc + nrm * margin)
        stats["moved"] += 1
        stats["regions"][key] = stats["regions"].get(key, 0) + 1
    apply_positions(me, positions)

    inflated = 0
    for _ in range(rounds):
        need = _face_clearance(me, regions, tgt_bvhs)
        if max(need, default=0.0) <= 1e-6:
            break
        dirs = _clearance_directions(me, regions, tgt_bvhs)
        dirs = _smooth_field(dirs, me, iterations=3)
        need = _blend_field(me, need, iterations=2)
        positions = []
        moved = 0
        for i, v in enumerate(me.vertices):
            depth = need[i]
            x, y, z = dirs[i]
            length = (x * x + y * y + z * z) ** 0.5
            if depth > 1e-6 and length > 1e-9:
                moved += 1
                scale = depth / length
                if depth > max_push:
                    scale = max_push / length
                x, y, z = x * scale, y * scale, z * scale
            else:
                x = y = z = 0.0
            positions.append(v.co + Vector((x, y, z)))
        apply_positions(me, positions)
        inflated += moved
    stats["inflated"] = inflated
    return stats


def _clearance_directions(me: bpy.types.Mesh, regions: list[str | None],
                          tgt_bvhs: dict[str, BVHTree]
                          ) -> list[tuple[float, float, float]]:
    """Per vertex: the outward normal of the base body next to it."""
    out: list[tuple[float, float, float]] = []
    for i, v in enumerate(me.vertices):
        key = regions[i]
        bvh = tgt_bvhs.get(key) if key else None
        if bvh is None:
            out.append((0.0, 0.0, 0.0))
            continue
        loc, nrm, _k, _dist = bvh.find_nearest(v.co)
        if loc is None or nrm.length < 1e-6:
            out.append((0.0, 0.0, 0.0))
            continue
        out.append((nrm.x, nrm.y, nrm.z))
    return out


def _blend_field(me: bpy.types.Mesh, field: list[float],
                 iterations: int = 2) -> list[float]:
    """Soften a per vertex field, but keep the peaks.

    A plain average would flatten the field completely - a single face that
    dips deep into the body would barely move the vertices around it.
    """
    adj: list[list[int]] = [[] for _ in field]
    for p in me.polygons:
        vs = list(p.vertices)
        for i in vs:
            for j in vs:
                if i != j and j not in adj[i]:
                    adj[i].append(j)
    cur = list(field)
    for _ in range(iterations):
        nxt = list(cur)
        for i, nbrs in enumerate(adj):
            if not nbrs:
                continue
            avg = sum(cur[j] for j in nbrs) / len(nbrs)
            nxt[i] = 0.7 * cur[i] + 0.3 * avg
        cur = nxt
    return cur


def _face_clearance(me: bpy.types.Mesh, regions: list[str | None],
                    tgt_bvhs: dict[str, BVHTree]) -> list[float]:
    """Per vertex: how deep the outfit still is inside the base body.

    The depth is measured on the face centre and on the edge mid points - a
    face whose centre is outside can still dip into the skin with its edges.
    """
    req = [0.0] * len(me.vertices)
    for p in me.polygons:
        vs = list(p.vertices)
        if not vs:
            continue
        key = regions[vs[0]]
        if key is None or any(regions[i] != key for i in vs):
            continue
        bvh = tgt_bvhs.get(key)
        if bvh is None:
            continue
        center = Vector((0.0, 0.0, 0.0))
        for i in vs:
            center += me.vertices[i].co
        center /= len(vs)
        points = [center]
        for k in range(len(vs)):
            a = me.vertices[vs[k]].co
            b = me.vertices[vs[(k + 1) % len(vs)]].co
            points.append((a + b) * 0.5)
        need = 0.0
        for q in points:
            loc, nrm, _i, dist = bvh.find_nearest(q)
            if loc is None or nrm.length < 1e-6:
                continue
            if (q - loc).dot(nrm) >= 0.0:
                continue
            if dist > need:
                need = dist
        if need <= 0.0:
            continue
        for i in vs:
            if need > req[i]:
                req[i] = need
    return req


def limb_extents(body_meshes: list[bpy.types.Object],
                 min_weight: float = 0.3) -> dict[str, dict[str, list[float]]]:
    """The world space bounding box of every hand / foot region of a body."""
    out: dict[str, dict[str, list[float]]] = {}
    for obj in body_meshes:
        mw = obj.matrix_world
        for i, key in enumerate(_vertex_limb(obj, min_weight)):
            if not key:
                continue
            co = mw @ obj.data.vertices[i].co
            rec = out.setdefault(key, {"min": [1e9] * 3, "max": [-1e9] * 3})
            for k in range(3):
                rec["min"][k] = min(rec["min"][k], co[k])
                rec["max"][k] = max(rec["max"][k], co[k])
    return out


def scale_limb_forward(garment: bpy.types.Object, regions: list[str | None],
                        tgt_extents: dict[str, dict[str, list[float]]],
                        tgt_arm: bpy.types.Object,
                        keys=("foot_L", "foot_R")) -> dict[str, float]:
    """Let the outfit's foot reach as far forward as the base body's foot.

    The shoe was modelled for a smaller foot, so after the retarget it stops
    short of the toes and they stick out in front of it.  The shoe is stretched
    along the foot's length until its front matches the base body's.
    """
    me = garment.data
    out: dict[str, float] = {}
    for key in keys:
        ext = tgt_extents.get(key)
        if not ext:
            continue
        side = "L" if key.endswith("L") else "R"
        bone = tgt_arm.data.bones.get(f"足首D.{side}")
        if bone is not None:
            anchor = (tgt_arm.matrix_world @ bone.head_local).y
        else:
            anchor = (ext["min"][1] + ext["max"][1]) * 0.5
        garment_y = [me.vertices[i].co.y for i, r in enumerate(regions) if r == key]
        if not garment_y:
            continue
        boot_min = min(garment_y)
        span_g = anchor - boot_min
        span_t = anchor - ext["min"][1]
        if span_g <= 1e-4 or span_t <= 1e-4:
            continue
        factor = span_t / span_g
        if factor <= 1.002:
            continue
        positions = [v.co.copy() for v in me.vertices]
        for i, r in enumerate(regions):
            if r != key:
                continue
            positions[i].y = anchor + (positions[i].y - anchor) * factor
        apply_positions(me, positions)
        out[key] = factor
    return out


def geometric_tightness(garment: bpy.types.Object, tgt_bvh: BVHTree,
                          body_bones: set[str], snug: float = 0.015
                          ) -> list[float]:
    """How tight a piece of the outfit sits on the base body.

    The bone is a bad proxy for this: the hem of a skirt is bound to a leg
    bone, so it counts as "body", but the skirt is loose there and pulling it
    onto the body folds the skirt up.  The distance to the body says it
    directly - a part that already lies on the body is tight, a part that
    hangs a few centimetres away is loose and keeps its shape.
    """
    dom = dominant_bones(garment)
    out = []
    for i, v in enumerate(garment.data.vertices):
        # both have to hold: the part has to be driven by a body bone *and*
        # it has to lie on the body.  A ribbon or a skirt lining hangs close
        # to the leg but is driven by its own chain, and pulling that onto
        # the body folds the outfit up.
        if dom[i].split(".")[0] not in body_bones:
            out.append(0.0)
            continue
        loc, _n, _i, dist = tgt_bvh.find_nearest(v.co)
        out.append(1.0 if (loc is not None and dist <= snug) else 0.0)
    return out


def body_bone_tightness(garment: bpy.types.Object, body_bones: set[str]
                        ) -> list[float]:
    """Per vertex: 1 = driven by body bones (tight), 0 = by garment bones.

    This is the plan's region split: the bodice follows the body, the skirt
    and the flared sleeves keep their silhouette.

    The *dominant* bone decides, not the summed weight: a flared sleeve is
    anchored to the upper arm bone but hangs off its own chain, and summing
    the weights would call the whole sleeve "tight" and collapse it onto the
    arm.
    """
    names = [vg.name for vg in garment.vertex_groups]
    out = []
    for v in garment.data.vertices:
        wb = 0.0
        wg = 0.0
        for g in v.groups:
            if g.weight <= 0.0:
                continue
            name = names[g.group]
            # the mmd_tools helper groups (mmd_edge_scale and friends) sit on
            # every vertex with a weight of 1.0; counting them would make every
            # vertex look like it is driven by a garment bone
            if name.startswith(AUX_GROUPS):
                continue
            if name in body_bones:
                wb = max(wb, g.weight)
            else:
                wg = max(wg, g.weight)
        # The body bone has to win outright.  A soft transition over the
        # difference pulls the edges of the skirt (which are partly bound to
        # the waist) onto the body and folds the skirt up.
        out.append(wb if wb > wg else 0.0)
    return out


def _smooth_field(values: list[tuple[float, float, float]], mesh, iterations=2):
    """Average a per-vertex vector field over the mesh edges."""
    if not values or iterations <= 0:
        return values
    n = len(values)
    adj: list[list[int]] = [[] for _ in range(n)]
    for e in mesh.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    cur = list(values)
    for _ in range(iterations):
        nxt = []
        for i, (x, y, z) in enumerate(cur):
            if not adj[i]:
                nxt.append((x, y, z))
                continue
            sx = sy = sz = 0.0
            for j in adj[i]:
                v = cur[j]
                sx += v[0]
                sy += v[1]
                sz += v[2]
            k = len(adj[i])
            nxt.append((x * 0.5 + sx / k * 0.5, y * 0.5 + sy / k * 0.5,
                        z * 0.5 + sz / k * 0.5))
        cur = nxt
    return cur


def fit_to_body(garment: bpy.types.Object, target_bvh: BVHTree,
                tightness: list[float], offset: float = 0.005,
                strength: float = 0.85, max_pull: float = 0.12,
                max_fit_dist: float = 0.05) -> dict[str, Any]:
    """Pull the tight parts of the garment onto the target body.

    A vertex that is far away from the body is not "tight" - it belongs to a
    loose part of the outfit - so it is left alone. Without that guard a
    sleeve would be dragged across the whole body.
    """
    me = garment.data
    corrections = []
    moved = 0
    skipped = 0
    max_dist = 0.0
    for v in me.vertices:
        t = tightness[v.index]
        if t <= 0.001:
            corrections.append((0.0, 0.0, 0.0))
            continue
        loc, nrm, _idx, dist = target_bvh.find_nearest(v.co)
        if loc is None or dist > max_fit_dist:
            corrections.append((0.0, 0.0, 0.0))
            skipped += 1
            continue
        desired = loc + nrm * offset
        delta = (desired - v.co) * (t * strength)
        if delta.length > max_pull:
            delta = delta.normalized() * max_pull
        corrections.append(tuple(delta))
        max_dist = max(max_dist, delta.length)
        if delta.length > 1e-5:
            moved += 1

    corrections = _smooth_field(corrections, me, iterations=2)
    new_positions = [v.co + Vector(corrections[v.index]) for v in me.vertices]
    apply_positions(me, new_positions)

    return {"vertices_fitted": moved, "vertices_skipped_far": skipped,
            "max_pull": round(max_dist, 5)}


# --------------------------------------------------------------------------
# Body masking
# --------------------------------------------------------------------------


def _count_crossings(bvh: BVHTree, origin: Vector, direction: Vector,
                      max_dist: float) -> int:
    """How many times a ray crosses the (closed) garment surface."""
    count = 0
    o = origin.copy()
    d = direction.normalized()
    remaining = max_dist
    while remaining > 1e-5:
        loc, _nrm, _idx, dist = bvh.ray_cast(o, d, remaining)
        if loc is None:
            break
        count += 1
        step = dist + 1e-4
        o = loc + d * step
        remaining -= step
        if count > 24:
            break
    return count


def garment_boundary_points(garment: bpy.types.Object) -> list[Vector]:
    """The vertices on the open edges of the garment.

    A garment is a shell with openings - the cuff of a glove, the mouth of a
    shoe, the hem of a skirt.  Body points that sit at such an opening are
    *not* covered, they are visible, so they must be kept.
    """
    me = garment.data
    edge_use: dict[tuple[int, int], int] = {}
    for poly in me.polygons:
        vs = list(poly.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            key = (a, b) if a < b else (b, a)
            edge_use[key] = edge_use.get(key, 0) + 1
    out = []
    for (a, b), n in edge_use.items():
        if n == 1:
            out.append(me.vertices[a].co.copy())
            out.append(me.vertices[b].co.copy())
    return out


def source_coverage(src_body: bpy.types.Object, garment_bvh: BVHTree,
                    face_indices: list[int], max_dist: float = 0.012,
                    margin: int = 0, garment: bpy.types.Object | None = None,
                    opening_clearance: float = 0.03,
                    ignore_materials: tuple[str, ...] = (),
                    snug_limit: float = 0.006) -> dict[int, bool]:
    """Which source body *faces* are covered by the clothes.

    The test is "is the body point inside the garment", not "is the garment
    in front of the body point".  The difference matters: a glove or a shoe is
    a shell that *encloses* the fingers, so the nearest cloth point is to the
    side of the finger, not in front of it - the old test left the fingers
    uncovered and they poked through the glove.

    Two ways to be covered, both requiring the cloth to be close:
      * the cloth is right in front of the body (a bodice on the chest)
      * the cloth is a shell around the body (a glove round the fingers)
    A skirt hangs several centimetres away and is see through, so the leg
    under it has to stay.

    The result is per *face*, not per vertex: a source leg can be one huge
    face, and a per vertex answer would tear the covered area into pieces
    when it is transferred to the target.
    """
    me = src_body.data
    mw = src_body.matrix_world

    from mathutils.kdtree import KDTree
    openings: KDTree | None = None
    if garment is not None:
        pts = garment_boundary_points(garment)
        if pts:
            openings = KDTree(len(pts))
            for p in pts:
                openings.insert(p, 0)
            openings.balance()

    face_covered: dict[int, bool] = {}
    for fi in face_indices:
        poly = me.polygons[fi]
        verts = list(poly.vertices)
        if not verts:
            face_covered[fi] = False
            continue
        # Some garments are layered and see through - a skirt has an inner
        # lining that sits right on the leg.  Hiding the body under such a
        # garment leaves a hole that shows through the fabric, so those
        # materials are left out of the coverage.
        if ignore_materials:
            mi = poly.material_index
            mname = me.materials[mi].name if mi < len(me.materials) else ""
            if mname and mname in ignore_materials:
                face_covered[fi] = False
                continue
        hits = 0
        for vi in verts:
            co = mw @ me.vertices[vi].co
            loc, _nrm, _idx, dist = garment_bvh.find_nearest(co)
            if loc is None or dist > max_dist:
                continue
            if openings is not None:
                _p, _i, odist = openings.find(co)
                if odist <= opening_clearance:
                    continue
            n = (mw.to_3x3() @ me.vertices[vi].normal).normalized()
            in_front = (loc - co).dot(n) > 0.0
            if in_front:
                hits += 1
        # a face counts as covered when most of its vertices are
        face_covered[fi] = hits * 2 >= len(verts)
    if margin > 0:
        adj: dict[int, set[int]] = {fi: set() for fi in face_indices}
        for e in me.edges:
            for fi in face_indices:
                if e.vertices[0] in me.polygons[fi].vertices and \
                        e.vertices[1] in me.polygons[fi].vertices:
                    pass
        # erode over face adjacency
        fmap: dict[int, set[int]] = {fi: set() for fi in face_indices}
        for e in me.edges:
            for fi in face_indices:
                if e.vertices[0] in me.polygons[fi].vertices and \
                        e.vertices[1] in me.polygons[fi].vertices:
                    fmap[fi].add(fi)
        for _ in range(margin):
            face_covered = {fi: (face_covered[fi] and
                                 all(face_covered.get(g, False)
                                     for g in fmap[fi]))
                            for fi in face_indices}
    return face_covered

def transfer_coverage(target_body: bpy.types.Object, src_body: bpy.types.Object,
                      covered: dict[int, bool],
                      src_vertices: list[int] | None = None,
                      max_dist: float = 0.04,
                      z_limit: float = float("inf"),
                      garment_bvh: BVHTree | None = None,
                      snug_dist: float = 0.02) -> list[int]:
    """Map the source coverage onto the target body; return faces to delete.

    The mapping is face to face: every target face finds the nearest source
    face and inherits its covered flag.  Going through the vertices instead
    lets a handful of covered points tear the area into patches, because the
    nearest covered point is found for every single face.
    """
    from mathutils.kdtree import KDTree

    me = src_body.data
    mw = src_body.matrix_world
    kd = KDTree(len(covered))
    for fi in covered:
        kd.insert(mw @ me.polygons[fi].center, fi)
    kd.balance()

    tme = target_body.data
    tmw = target_body.matrix_world
    delete = []
    for poly in tme.polygons:
        center = tmw @ poly.center
        if center.z > z_limit:
            continue
        _c, index, dist = kd.find(center)
        if index is None or dist > max_dist:
            continue
        if not covered.get(index, False):
            continue
        if garment_bvh is not None:
            # The body has to really lie against the cloth.  A skirt hangs
            # several centimetres away and is see through, so the leg under it
            # has to stay - hiding it would leave a hole behind the fabric.
            loc, _nrm, _idx, gdist = garment_bvh.find_nearest(center)
            if loc is None or gdist > snug_dist:
                continue
        delete.append(poly.index)
    return delete

def inside_garment(garment_bvh: BVHTree, point: Vector,
                   max_dist: float = 0.8) -> bool:
    """Is the point inside the garment shell?

    A single ray is not enough - an open garment (a skirt, a sleeve) breaks
    the parity test. Voting over six directions is: a point really inside
    crosses the shell on almost every direction, a point merely next to the
    garment only on the one pointing at it.
    """
    odd = 0
    for d in _CONTAIN_DIRS:
        if _count_crossings(garment_bvh, point, d, max_dist) % 2 == 1:
            odd += 1
    return odd > len(_CONTAIN_DIRS) / 2


def hair_inside_garment(target_body: bpy.types.Object, garment_bvh: BVHTree,
                        hair_faces: list[int], max_dist: float = 0.04
                        ) -> list[int]:
    """Hair strands that end up inside the clothes (long hair of the base body).

    The hair has no counterpart on the source model, so the coverage transfer
    cannot help here - the test is done directly on the target.
    """
    me = target_body.data
    mw = target_body.matrix_world
    doomed = []
    for fi in hair_faces:
        center = mw @ me.polygons[fi].center
        loc, _nrm, _idx, dist = garment_bvh.find_nearest(center)
        if loc is None or dist > max_dist:
            continue
        if inside_garment(garment_bvh, center):
            doomed.append(fi)
    return doomed


def _is_transparent(mat: bpy.types.Material | None) -> bool:
    """Is this MMD material see-through?

    Body under a transparent garment has to stay: deleting it would make the
    cloth look hollow instead of showing the skin through the fabric.
    """
    if mat is None:
        return True
    try:
        mmd = mat.mmd_material
        if getattr(mmd, "alpha_mode", "OPAQUE") == "BLEND":
            return True
        if getattr(mmd, "alpha", 1.0) < 0.99:
            return True
    except Exception:
        pass
    try:
        if mat.blend_method in ('BLEND', 'HASHED', 'CLIP'):
            return True
    except Exception:
        pass
    return False


def mask_by_garment(target_body: bpy.types.Object, garment: bpy.types.Object,
                    garment_bvh: BVHTree, max_dist: float = 0.015
                    ) -> tuple[list[int], int]:
    """Hide the body that the clothes actually cover.

    Now that the garment really sits on the base body (the fit pulled the
    tight areas onto it), the covered body can be found directly: a body
    point is covered when a piece of *opaque* cloth sits just outside it,
    along the body normal.

    The earlier approach measured the coverage on the source model and
    transferred it, which misfired on the ribbons hanging next to the legs:
    they are in front of the leg, so the leg counted as covered and a hole
    appeared.  Here the distance also has to be small, so a ribbon a few
    centimetres away does not count.
    """
    me = target_body.data
    mw = target_body.matrix_world
    gme = garment.data
    covered_v: dict[int, bool] = {}
    for v in me.vertices:
        co = mw @ v.co
        n = (mw.to_3x3() @ v.normal).normalized()
        loc, _nrm, idx, dist = garment_bvh.find_nearest(co)
        if loc is None or dist > max_dist:
            covered_v[v.index] = False
            continue
        if (loc - co).dot(n) <= 0.0:
            covered_v[v.index] = False
            continue
        gmat = None
        if idx is not None and idx < len(gme.polygons):
            mi = gme.polygons[idx].material_index
            if mi < len(gme.materials):
                gmat = gme.materials[mi]
        covered_v[v.index] = not _is_transparent(gmat)

    doomed = []
    for poly in me.polygons:
        vs = poly.vertices
        if vs and all(covered_v.get(i, False) for i in vs):
            doomed.append(poly.index)
    return doomed, sum(1 for c in covered_v.values() if c)


def hide_faces_with_material(body: bpy.types.Object,
                              face_indices: list[int]) -> int:
    """Hide body faces by moving them to a transparent material.

    Deleting the faces works, but the vertices that border the hole end up
    with a normal that only averages the surviving faces, and the MMD toon
    shader paints those borders black - the body comes out with a row of
    jagged black stripes.  A transparent material leaves the topology (and
    with it the weights and the morphs) untouched and has no such edge.
    """
    if not face_indices:
        return 0
    me = body.data
    mat = bpy.data.materials.get("__mmd_hidden__")
    if mat is None:
        mat = bpy.data.materials.new("__mmd_hidden__")
        mat.use_nodes = True
        # the alpha has to be on the shader as well - mmd_tools computes the
        # alpha of a real MMD material in its node group, a plain material
        # would stay opaque and paint a black patch over the body
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                node.inputs["Alpha"].default_value = 0.0
            if node.type == 'BSDF_TRANSPARENT':
                mat.node_tree.links.new(node.outputs[0],
                                       node.inputs[0]) if False else None
        try:
            mat.blend_method = 'BLEND'
        except Exception:
            pass
        try:
            mat.surface_render_method = 'BLENDED'
        except Exception:
            pass
        try:
            mmd = mat.mmd_material
            mmd.alpha = 0.0
            mmd.is_double_sided = True
        except Exception:
            pass
    index = None
    for i, m in enumerate(me.materials):
        if m is mat:
            index = i
            break
    if index is None:
        me.materials.append(mat)
        index = len(me.materials) - 1
    for fi in face_indices:
        me.polygons[fi].material_index = index
    me.update()
    return len(face_indices)


def neck_height(armature: bpy.types.Object) -> float:
    """World Z of the neck bone - everything above it is head, never masked."""
    for name in ("首", "neck", "Neck"):
        bone = armature.data.bones.get(name)
        if bone is not None:
            return (armature.matrix_world @ bone.head_local).z
    return float("inf")


def delete_faces(obj: bpy.types.Object, face_indices: list[int]) -> int:
    """Remove faces from a mesh, keeping the vertex numbering intact.

    The vertex numbering has to stay stable because the shape keys and the
    vertex groups address vertices by index; deleting faces only leaves loose
    vertices behind, which MMD simply never draws.
    """
    if not face_indices:
        return 0
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    doomed = [bm.faces[i] for i in face_indices if i < len(bm.faces)]
    bmesh.ops.delete(bm, geom=doomed, context='FACES_ONLY')
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(face_indices)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


DEFAULT_CONFIG = {
    "fit": {
        "offset": 0.005,
        "strength": 0.85,
        "max_pull": 0.08,
        "max_fit_dist": 0.15,
        # Data-Transfer style weights from the base body.  Measured on
        # 刻晴 -> 达妮娅: switching it on raises the motion clipping from
        # 1.36% to 1.75% (and 0.3 and 0.8 give the same number), because the
        # garment already carries weights an artist tuned on its own body.
        # Off by default, kept for garments whose source weights are poor.
        # the glove and the shoe are the source's own finger and toe surfaces
        # (no thickness of their own), so they are laid back onto the base
        # body's hand and foot
        "fit_limbs": True,
        "limb_margin": 0.005,
        "limb_max_dist": 0.05,
        "limb_near_dist": 0.004,
        "limb_min_weight": 0.3,
        "limb_rounds": 4,
        "limb_max_push": 0.012,
        "scale_limbs": True,
        # fit the finger sleeves and the shoes onto the base body's limbs
        "fit_limb_ends": False,
        "limb_reach": 0.14,
        # a part of the outfit counts as tight when it lies this close to
        # the base body - the geometric measure is the right one, but the
        # selection still has to be narrowed down per part (a skirt hem is
        # bound to a leg bone but hangs loose there)
        "snug": 0.015,
        "use_tight_fit": False,
        "use_target_weights": False,
        "target_weight_blend": 0.8,
    },
    "body_mask": {
        "enabled": True,
        # "direct" measures the coverage on the target itself, "source"
        # measures it on the source model and transfers it
        "method": "source",
        # how close the cloth has to be for the body under it to count as
        # covered - a skirt hangs further away and is see through
        "cover_dist": 0.012,
        # body points this close to an opening of the garment stay visible
        "opening_clearance": 0.03,
        "max_dist": 0.08,
        "hair_max_dist": 0.04,
        "hair": True,
        "margin": 0,
        # "material" hides the covered body with a transparent material,
        # "delete" removes the faces (cleaner in MMD, but leaves jagged
        # shading along the hole on the base body)
        "mode": "material",
        # the body has to lie against the cloth to be hidden
        "snug_dist": 0.02,
        # layered, see through garments: the body under them has to stay
        "ignore_materials": ["裙"],
        # how tight a shell has to be around the body to count as covering it
        "snug_limit": 0.003,
    },
    "physics": {
        # P3-02: copy the outfit's rigid bodies and joints to the target
        "enabled": True,
    },
    "motion": {
        # Off by default on purpose: the pose suite has to evaluate and
        # temporarily modify the rig, and that must never touch the model
        # that gets exported.  Use `python -m src.cli motion-check` on the
        # finished PMX instead.
        "enabled": False,
        "render": True,
        "repair": True,
    },
}


def _load_config(path: str | None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path:
        return cfg
    p = Path(path)
    if not p.exists():
        return cfg
    user = json.loads(p.read_text(encoding="utf-8"))
    for key in ("fit", "body_mask", "motion"):
        if key in user and isinstance(user[key], dict):
            cfg[key].update(user[key])
    return cfg


def _armature_of(objects: list[bpy.types.Object]) -> bpy.types.Object | None:
    for o in objects:
        if o.type == 'ARMATURE':
            return o
    return None


def run(src_objs: list[bpy.types.Object], tgt_objs: list[bpy.types.Object],
        out_dir: str, config_path: str | None = None,
        selection: dict[str, Any] | None = None,
        stages: bool = False) -> dict[str, Any]:
    """Full pipeline: extract -> retarget -> fit -> mask -> export."""
    from . import extraction, garment as garment_mod, import_export as ie

    cfg = _load_config(config_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    src_body_meshes = ie.model_meshes(src_objs)
    tgt_body_meshes = ie.model_meshes(tgt_objs)
    if not src_body_meshes or not tgt_body_meshes:
        raise RuntimeError("both models need a body mesh")

    src_arm = _armature_of(src_objs)
    tgt_arm = _armature_of(tgt_objs)
    if src_arm is None or tgt_arm is None:
        raise RuntimeError("both models need an armature")

    # ---- P1-01/02: which parts, and cut them out ----
    src_body = src_body_meshes[0]
    parts = extraction.enumerate_parts(src_body_meshes)
    bbox = extraction._scene_bbox(src_body_meshes)
    height = bbox[1][2] - bbox[0][2]
    classified = extraction.classify_parts(parts, height, bbox)
    if not selection:
        selection = extraction.suggest_selection(
            classified, extraction.material_table(classified))

    cloth_faces = {p["mesh"]: [] for p in classified}
    for p in classified:
        if p["id"] in set(selection.get("selected_parts", [])):
            cloth_faces[p["mesh"]].extend(p["faces"])

    extracted = garment_mod.extract_clothing(
        src_objs, classified, selection.get("selected_parts", []),
        str(out / "extracted"), name="Cloth")
    cloth = extracted["cloth"]
    used_bones = set(extracted["summary"]["used_bones"])

    mask_stats: dict[str, Any] = {"enabled": cfg["body_mask"]["enabled"],
                                   "deleted_faces": 0}

    # ---- the coverage has to be measured in the source's coordinates ----
    # The garment is still sitting on the source body here; after the
    # retarget it is six centimetres away and the containment test would
    # compare two different coordinate systems.
    cloth_faces_all = set()
    for faces in cloth_faces.values():
        cloth_faces_all.update(faces)
    src_skin_faces = [fi for fi in body_faces(src_body, skip_hair=True,
                                               skip_face=True)
                      if fi not in cloth_faces_all]
    src_skin_verts = sorted({v for fi in src_skin_faces
                              for v in src_body.data.polygons[fi].vertices})
    coverage = source_coverage(src_body, build_bvh(cloth[0]), src_skin_faces,
                               max_dist=cfg["body_mask"].get("cover_dist",
                                                             0.012),
                               margin=cfg["body_mask"].get("margin", 0),
                               garment=cloth[0],
                               opening_clearance=cfg["body_mask"].get(
                                   "opening_clearance", 0.03),
                               ignore_materials=tuple(cfg["body_mask"].get(
                                   "ignore_materials", ("裙",))),
                               snug_limit=cfg["body_mask"].get("snug_limit",
                                                              0.003))
    mask_stats["source_covered_faces"] = sum(1 for v in coverage.values() if v)

    # ---- P1-03: rig map + rest pose deltas ----
    rig_map = build_rig_map(src_arm, tgt_arm, used_bones)
    deltas = rest_deltas(src_arm, tgt_arm, rig_map["mapping"])
    g_deltas = garment_deltas(src_arm, rig_map["garment_bones"], deltas)
    all_deltas = dict(deltas)
    all_deltas.update(g_deltas)

    specs = garment_bone_specs(src_arm, rig_map["garment_bones"], all_deltas)
    created = add_bones(tgt_arm, specs)

    stage_images: dict[str, list[str]] = {}

    def snapshot(tag: str) -> None:
        if not stages:
            return
        for o in src_objs:
            o.hide_render = True
        objs = list(tgt_body_meshes) + list(cloth)
        stage_images[tag] = extraction.render_objects(
            objs, out / "stages", prefix=tag)
        for o in src_objs:
            o.hide_render = False

    snapshot("stage1_extracted")

    # ---- P1-05: re-skin the garment onto the target rig ----
    bone_map = dict(rig_map["mapping"])
    for name in rig_map["garment_bones"]:
        bone_map[name] = name
    reskin_stats = reskin(cloth[0], all_deltas, bone_map) if cloth else {}

    # bind the garment to the target armature
    for c in cloth:
        for m in list(c.modifiers):
            if m.type == 'ARMATURE':
                c.modifiers.remove(m)
        mod = c.modifiers.new(name="Armature", type='ARMATURE')
        mod.object = tgt_arm
        c.parent = tgt_arm
        c.parent_type = 'OBJECT'
        c.matrix_parent_inverse = tgt_arm.matrix_world.inverted()

    snapshot("stage2_reskinned")

    # ---- P1-04: fit the garment onto the target body ----
    tgt_skin_faces: list[int] = []
    for m in tgt_body_meshes:
        tgt_skin_faces.extend(body_faces(m, skip_hair=True, skip_face=True))
    tgt_bvh = build_bvh(tgt_body_meshes[0], tgt_skin_faces) \
        if len(tgt_body_meshes) == 1 else _merge_bvh(tgt_body_meshes, tgt_skin_faces)

    body_bones = set(rig_map["mapping"].keys())
    if cloth and cfg["fit"].get("use_tight_fit", False):
        tightness = geometric_tightness(cloth[0], tgt_bvh, body_bones,
                                       cfg["fit"].get("snug", 0.015))
    else:
        tightness = ([0.0] * len(cloth[0].data.vertices) if cloth else [])

    # P1-05: let the tight parts follow the *target* body's weight gradient
    reweight_stats: dict[str, Any] = {}
    if cloth and cfg["fit"].get("use_target_weights", True):
        reweight_stats = transfer_target_weights(
            cloth[0], tgt_body_meshes[0], body_bones, tightness,
            blend=cfg["fit"].get("target_weight_blend", 0.8))

    fit_stats = fit_to_body(cloth[0], tgt_bvh, tightness,
                            offset=cfg["fit"]["offset"],
                            strength=cfg["fit"]["strength"],
                            max_pull=cfg["fit"]["max_pull"],
                            max_fit_dist=cfg["fit"]["max_fit_dist"]) if cloth else {}

    # The glove and the shoe are the source's own finger and toe surfaces, so
    # they have to be laid back onto the base body's hand and foot - they are
    # buried inside it otherwise, because the base body has the bigger hands.
    limb_fit_stats: dict[str, Any] = {}
    if cloth and cfg["fit"].get("fit_limbs", True):
        tgt_limb_bvhs = limb_bvhs(tgt_body_meshes,
                                  cfg["fit"].get("limb_min_weight", 0.3))
        # the shoe has to reach as far forward as the base body's foot
        forward = scale_limb_forward(
            cloth[0], limb_regions(cloth[0]),
            limb_extents(tgt_body_meshes, cfg["fit"].get("limb_min_weight", 0.3)),
            tgt_arm) if cfg["fit"].get("scale_limbs", True) else {}
        limb_fit_stats = fit_limb_regions(
            cloth[0], tgt_limb_bvhs,
            margin=cfg["fit"].get("limb_margin", 0.003),
            max_dist=cfg["fit"].get("limb_max_dist", 0.05),
            near_dist=cfg["fit"].get("limb_near_dist", 0.004),
            rounds=cfg["fit"].get("limb_rounds", 4),
            max_push=cfg["fit"].get("limb_max_push", 0.012))
        limb_fit_stats["forward_scale"] = forward

    limb_stats: dict[str, Any] = {}
    if cloth and cfg["fit"].get("fit_limb_ends", False):
        limb_stats = fit_limb_ends(cloth[0], tgt_body_meshes[0], tgt_arm, tgt_bvh,
                                    max_reach=cfg["fit"].get("limb_reach", 0.14))

    snapshot("stage3_fitted")

    # ---- P2: high risk pose suite, before the body gets holes ----
    motion_stats: dict[str, Any] = {"enabled": cfg["motion"]["enabled"]}
    if cfg["motion"]["enabled"] and cloth:
        from . import motion as motion_mod
        scene_objs = list(tgt_objs) + list(cloth)
        before = motion_mod.run_pose_suite(
            scene_objs, None, str(out / "motion" / "before"),
            render=cfg["motion"]["render"])
        motion_stats["before"] = {
            "rest_pierced": before.get("rest_pierced"),
            "worst": before.get("worst", {}).get("pose") if before.get("worst") else None,
            "worst_pierced": before.get("worst", {}).get("pierced") if before.get("worst") else None,
        }
        if cfg["motion"]["repair"] and before.get("worst"):
            worst_pose = next((p for p in motion_mod.POSES
                               if p["name"] == before["worst"]["pose"]), None)
            if worst_pose is not None:
                doomed = motion_mod.poking_body_faces(scene_objs, worst_pose)
                removed = delete_faces(tgt_body_meshes[0], doomed)
                motion_stats["repair"] = {
                    "pose": worst_pose["name"],
                    "category": worst_pose["category"],
                    "faces_deleted": removed,
                }
        after = motion_mod.run_pose_suite(
            scene_objs, None, str(out / "motion" / "after"),
            render=cfg["motion"]["render"])
        motion_stats["after"] = {
            "rest_pierced": after.get("rest_pierced"),
            "worst": after.get("worst", {}).get("pose") if after.get("worst") else None,
            "worst_pierced": after.get("worst", {}).get("pierced") if after.get("worst") else None,
        }
        motion_stats["report"] = {
            "before": before.get("report_file"),
            "after": after.get("report_file"),
        }
        snapshot("stage3b_motion")

    # ---- P1-06: hide the covered body ----
    if cfg["body_mask"]["enabled"] and cloth:
        garment_bvh = build_bvh(cloth[0])
        method = cfg["body_mask"].get("method", "direct")
        if method == "source":
            # the coverage was measured in the source's coordinates, before
            # the retarget moved the garment
            to_delete = transfer_coverage(tgt_body_meshes[0], src_body, coverage,
                                          src_skin_verts,
                                          max_dist=cfg["body_mask"]["max_dist"],
                                          z_limit=neck_height(tgt_arm),
                                          garment_bvh=garment_bvh,
                                          snug_dist=cfg["body_mask"].get(
                                              "snug_dist", 0.02))
            pass
        else:
            # direct: the body that the clothes really cover on the target
            to_delete, covered_points = mask_by_garment(
                tgt_body_meshes[0], cloth[0], garment_bvh,
                max_dist=cfg["body_mask"].get("cover_dist", 0.015))
            z_limit = neck_height(tgt_arm)
            to_delete = [fi for fi in to_delete
                         if (tgt_body_meshes[0].matrix_world
                             @ tgt_body_meshes[0].data.polygons[fi].center).z
                         <= z_limit]
            mask_stats["covered_points"] = covered_points
            mask_stats["method"] = "direct"
        if cfg["body_mask"].get("mode", "material") == "delete":
            mask_stats["deleted_faces"] = delete_faces(tgt_body_meshes[0],
                                                       to_delete)
            mask_stats["mask_mode"] = "delete"
        else:
            mask_stats["deleted_faces"] = hide_faces_with_material(
                tgt_body_meshes[0], to_delete)
            mask_stats["mask_mode"] = "material"

        if cfg["body_mask"].get("hair", True):
            hair_faces = []
            for m in tgt_body_meshes:
                for fi in range(len(m.data.polygons)):
                    if _material_is(m, m.data.polygons[fi].material_index,
                                    HAIR_WORDS):
                        hair_faces.append((m, fi))
            hair_deleted = 0
            for m in tgt_body_meshes:
                faces = [fi for mm, fi in hair_faces if mm is m]
                if not faces:
                    continue
                doomed = hair_inside_garment(m, garment_bvh, faces,
                                             max_dist=cfg["body_mask"]
                                             .get("hair_max_dist", 0.04))
                hair_deleted += delete_faces(m, doomed)
            mask_stats["hair_faces_deleted"] = hair_deleted

    snapshot("stage4_masked")

    # ---- P3-02: migrate the outfit physics ----
    physics_stats: dict[str, Any] = {"enabled": cfg["physics"]["enabled"]}
    if cfg["physics"]["enabled"] and cloth:
        from . import physics as physics_mod
        physics_stats.update(physics_mod.migrate_physics(
            src_objs, list(tgt_objs) + list(cloth), src_arm, tgt_arm,
            all_deltas, set(rig_map["garment_bones"])))
        physics_stats["enabled"] = True
    else:
        physics_stats["enabled"] = False

    # ---- P1-07: export ----
    # the source model must not end up in the exported file
    for o in list(src_objs):
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass

    export = {}
    try:
        pmx_path = str(out / "model.pmx")
        ie.export_pmx(pmx_path, [o for o in tgt_objs if o.type in ('MESH', 'ARMATURE')])
        export["pmx"] = pmx_path
    except Exception as exc:                        # noqa: BLE001
        export["error"] = f"{type(exc).__name__}: {exc}"

    # ---- artifacts ----
    manifest = {
        "source": {"objects": len(src_objs)},
        "target": {"objects": len(tgt_objs)},
        "selection": selection,
        "rig_map": {
            "mapped_body_bones": rig_map["mapped_body_bones"],
            "garment_bones": rig_map["garment_bones"],
            "created_bones": created,
            "dropped_bones": rig_map["dropped_bones"],
        },
        "fit": {**fit_stats, "limbs": limb_fit_stats,
                "limb_ends": limb_stats,
                **reweight_stats, **cfg["fit"]},
        "body_bones": len(body_bones),
        "mask": mask_stats,
        "motion": motion_stats,
        "physics": physics_stats,
        "export": export,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "rig_map.json").write_text(
        json.dumps({"mapping": rig_map["mapping"],
                    "garment_bones": rig_map["garment_bones"],
                    "created_bones": created},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "fit_params.json").write_text(
        json.dumps({"fit": cfg["fit"], "stats": fit_stats,
                    "tightness_histogram": _histogram(tightness)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.json").write_text(
        json.dumps(_report(manifest), ensure_ascii=False, indent=1),
        encoding="utf-8")

    blend = out / "work.blend"
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True,
                                       do_recursive=True)
    except Exception:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    return {
        "out_dir": str(out),
        "pmx": export.get("pmx"),
        "blend": str(blend),
        "rig_map": manifest["rig_map"],
        "fit": manifest["fit"],
        "mask": mask_stats,
        "motion": motion_stats,
        "physics": physics_stats,
        "reskin": reskin_stats,
        "selected_materials": selection.get("selected_materials", []),
        "stage_images": stage_images,
    }


def _merge_bvh(meshes, face_indices):
    verts = []
    polys = []
    offset = 0
    for m in meshes:
        mw = m.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in m.data.vertices)
        polys.extend([[v + base for v in m.data.polygons[i].vertices]
                      for i in face_indices])
        offset = len(verts)
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def _histogram(values: list[float]) -> dict[str, int]:
    hist = {"0.0-0.2": 0, "0.2-0.5": 0, "0.5-0.8": 0, "0.8-1.0": 0}
    for v in values:
        if v < 0.2:
            hist["0.0-0.2"] += 1
        elif v < 0.5:
            hist["0.2-0.5"] += 1
        elif v < 0.8:
            hist["0.5-0.8"] += 1
        else:
            hist["0.8-1.0"] += 1
    return hist


def _report(manifest: dict[str, Any]) -> dict[str, Any]:
    items = []

    def add(name, status, detail):
        items.append({"check": name, "status": status, "detail": detail})

    rig = manifest["rig_map"]
    add("rig_mapping", "OK" if rig["mapped_body_bones"] else "FAILED",
        f"{len(rig['mapped_body_bones'])} body bones mapped, "
        f"{len(rig['created_bones'])} garment bones re-created")
    fit = manifest["fit"]
    add("body_fit", "OK" if fit.get("vertices_fitted") else "WARNING",
        f"{fit.get('vertices_fitted', 0)} vertices pulled onto the body")
    mask = manifest["mask"]
    add("body_mask", "OK" if mask.get("deleted_faces") else "WARNING",
        f"{mask.get('deleted_faces', 0)} body faces hidden")
    phys = manifest.get("physics", {})
    if phys.get("enabled") and phys.get("rigid_bodies"):
        add("outfit_physics", "OK",
            f"{phys['rigid_bodies']} rigid bodies and {phys['joints']} joints "
            f"migrated to the target")
    elif phys.get("enabled"):
        add("outfit_physics", "WARNING", phys.get("skipped", "nothing migrated"))
    motion = manifest.get("motion", {})
    if motion.get("enabled"):
        before = motion.get("before", {})
        after = motion.get("after", {})
        repair = motion.get("repair", {})
        add("motion_poses", "OK",
            f"worst pose {before.get('worst')}: {before.get('worst_pierced')} "
            f"-> {after.get('worst_pierced')} body points piercing the clothes"
            + (f"; repair removed {repair.get('faces_deleted')} body faces"
               if repair else ""))
    export = manifest["export"]
    add("pmx_export", "OK" if export.get("pmx") else "FAILED",
        export.get("pmx") or export.get("error", ""))
    return {"items": items,
            "status": "FAILED" if any(i["status"] == "FAILED" for i in items)
            else "OK"}
