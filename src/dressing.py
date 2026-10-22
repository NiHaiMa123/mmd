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
import math
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


# The fingers are so close together that a global "nearest face" search hands
# the index finger's weights to the middle finger.  Every digit gets its own
# search domain.
DIGIT_NAMES = (
    ("親指", "thumb"),
    ("人指", "index"),
    ("中指", "middle"),
    ("薬指", "ring"),
    ("小指", "little"),
)


def digit_domain(bone_name: str) -> str | None:
    """'人指１.L' -> 'index_L'; None when the bone is not a finger or a palm."""
    base = _bone_base(bone_name)
    side = _bone_side(bone_name)
    if not side:
        return None
    if base.startswith("手首"):
        return f"palm_{side}"
    for prefix, name in DIGIT_NAMES:
        if base.startswith(prefix):
            return f"{name}_{side}"
    return None


def _bvh_with_faces(obj: bpy.types.Object, face_indices: list[int]):
    """A BVH plus the mesh polygon index of every face inside it.

    `BVHTree.find_nearest` returns an index into the polygon list that was
    handed to the tree - not into the mesh.  The old code used that index on
    the mesh directly, so it read the weights of a completely different face.
    """
    me = obj.data
    mw = obj.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [list(me.polygons[i].vertices) for i in face_indices]
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    return tree, list(face_indices)


def transfer_target_weights(garment: bpy.types.Object,
                            target_body: bpy.types.Object,
                            body_bones: set[str], tightness: list[float],
                            blend: float = 0.8, max_dist: float = 0.06,
                            domains: bool = True,
                            always_regions: list[bool] | None = None
                            ) -> dict[str, Any]:
    """Give the tight parts of the garment the target body's weight gradient.

    The plan asks the skin weights to be taken from the base body by nearest
    face interpolation - that is what makes a garment follow the shoulders,
    armpit and hips of *this* body instead of the proportions of the body the
    garment was modelled on.  The loose parts (skirt, sleeves) keep their own
    garment bones.

    Two things make the plain version unusable on the hands:

    * the search has to stay inside the digit the vertex belongs to, otherwise
      the index finger picks up the middle finger's weights;
    * the fingers are tight by construction, but the geometric tightness
      measure cannot tell them apart, so they need their own gate
      (`always_regions`).
    """
    me = garment.data
    tme = target_body.data
    tmw = target_body.matrix_world
    gmw = garment.matrix_world
    skin_faces = body_faces(target_body, skip_hair=True, skip_face=True)

    # the faces of every search domain: a face belongs to a domain when all
    # of its vertices are driven by the same digit
    tdom = [digit_domain(n) for n in dominant_bones(target_body)]
    per_domain: dict[str, list[int]] = {}
    for fi in skin_faces:
        found = {tdom[i] for i in tme.polygons[fi].vertices} - {None}
        if len(found) != 1:
            continue
        per_domain.setdefault(found.pop(), []).append(fi)

    global_tree, global_faces = _bvh_with_faces(target_body, skin_faces)
    trees = {d: _bvh_with_faces(target_body, f) for d, f in per_domain.items()}

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

    gdom = [digit_domain(n) for n in dominant_bones(garment)]

    updated = 0
    for vi, v in enumerate(me.vertices):
        t = tightness[vi] * blend
        if always_regions is not None and always_regions[vi]:
            t = max(t, blend)
        if t <= 0.001:
            continue
        tree, faces = global_tree, global_faces
        if domains and gdom[vi] and gdom[vi] in trees:
            tree, faces = trees[gdom[vi]]
        # the trees are built in world space, so the query has to be too
        loc, _nrm, k, dist = tree.find_nearest(gmw @ v.co)
        if loc is None or dist > max_dist:
            continue
        poly = tme.polygons[faces[k]]
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
            # a body bone the garment did not carry yet: it comes from the
            # target only.  A bone that was already there was mixed in above,
            # adding it again would turn t into 2t.
            if name in body_bones and name not in current[vi]:
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
            "groups": len(buckets),
            "domains": len(trees)}


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
# The shoe: subdivide it, then lay it on the base body's foot
# --------------------------------------------------------------------------

def subdivide_shoe(garment: bpy.types.Object, bones=("足先EX",),
                    levels: int = 2) -> dict[str, Any]:
    """Subdivide the shoe's faces.

    The shoe is the source's own toe surface: it carries a few hundred
    vertices for the whole foot, while the base body's foot has thousands.
    Fitting such a coarse surface only moves it across the base body - the
    toes cut through it, because there is no vertex left to wrap them.
    Subdividing gives the fit enough vertices to do that.

    The vertex weights and the UVs survive the subdivision, so the shoe keeps
    its rig and its texture.
    """
    import bmesh

    me = garment.data
    stats: dict[str, Any] = {"levels": levels, "faces_before": len(me.polygons)}
    for level in range(levels):
        dom = dominant_bones(garment)
        face_ids = []
        for p in me.polygons:
            verts = list(p.vertices)
            if not verts:
                continue
            hits = sum(1 for v in verts if dom[v].split(".")[0] in bones)
            if hits >= len(verts) * 0.5:
                face_ids.append(p.index)
        stats[f"faces_level{level + 1}"] = len(face_ids)
        if not face_ids:
            hist: dict[str, int] = {}
            for b in dom:
                hist[b] = hist.get(b, 0) + 1
            stats["top_bones"] = sorted(hist.items(), key=lambda kv: -kv[1])[:12]
            break
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        edges = set()
        for fi in face_ids:
            f = bm.faces[fi]
            if f.is_valid:
                edges.update(f.edges)
        if not edges:
            bm.free()
            break
        bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1,
                                  use_grid_fill=False, smooth=0.0)
        bm.to_mesh(me)
        bm.free()
        stats[f"faces_after_level{level + 1}"] = len(me.polygons)
    stats["faces"] = len(me.polygons)
    stats["vertices"] = len(me.vertices)
    return stats


def _segment_distance(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    if ab.length_squared < 1e-12:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def foot_bvh(body_meshes: list[bpy.types.Object], arm: bpy.types.Object,
             side: str, max_radius: float = 0.13) -> BVHTree | None:
    """A BVH of the base body's foot only.

    The leg has to stay out of it.  The boot's shaft would be pulled onto the
    leg and collapse, which is what happened when the whole limb was
    projected.  The foot is everything within a hand's width of the line from
    the ankle to the toe tip.
    """
    a = arm.data.bones.get(f"足首D.{side}") or arm.data.bones.get(f"足首.{side}")
    b = arm.data.bones.get(f"つま先.{side}") or arm.data.bones.get(f"足先EX.{side}")
    if a is None or b is None:
        return None
    p0 = arm.matrix_world @ a.head_local
    p1 = arm.matrix_world @ b.tail_local

    verts: list[Vector] = []
    polys: list[list[int]] = []
    for obj in body_meshes:
        me = obj.data
        mw = obj.matrix_world
        base = len(verts)
        verts.extend([mw @ v.co for v in me.vertices])
        for p in me.polygons:
            ids = list(p.vertices)
            if not ids:
                continue
            if any(_segment_distance(verts[base + i], p0, p1) > max_radius
                   for i in ids):
                continue
            polys.append([i + base for i in ids])
    if not polys:
        return None
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def lay_shoe_on_foot(garment: bpy.types.Object, foot_bvh: BVHTree,
                     bones=("足先EX",), margin: float = 0.004,
                     max_dist: float = 0.06, blend_rings: int = 3,
                     falloff: float = 0.5) -> dict[str, Any]:
    """Put the shoe back onto the base body's foot.

    The shoe is the source's toe surface painted with the outfit material, so
    it has no thickness of its own: it has to lie *on* the base body's foot,
    not around it.  Its vertices are placed on the foot surface plus a small
    margin.

    The displacement is a field that fades out over the boot's shaft.  Moving
    the shoe alone would tear it away from the boot above it; letting the
    movement fade keeps the two connected.
    """
    me = garment.data
    dom = dominant_bones(garment)
    shoe = [i for i, b in enumerate(dom) if b in bones]
    stats: dict[str, Any] = {"shoe_vertices": len(shoe)}
    if not shoe:
        # the names do not match: report what is there instead of failing
        hist: dict[str, int] = {}
        for b in dom:
            hist[b] = hist.get(b, 0) + 1
        stats["top_bones"] = sorted(hist.items(), key=lambda kv: -kv[1])[:12]
        return stats
    disp: dict[int, Vector] = {}
    for i in shoe:
        v = me.vertices[i]
        loc, nrm, _idx, dist = foot_bvh.find_nearest(v.co)
        if loc is None or nrm.length < 1e-6 or dist > max_dist:
            continue
        disp[i] = (loc + nrm * margin) - v.co
    stats["placed"] = len(disp)
    if not disp:
        return stats

    adj: list[list[int]] = [[] for _ in range(len(me.vertices))]
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    current = set(disp)
    for _ in range(blend_rings):
        nxt: dict[int, Vector] = {}
        for i in range(len(me.vertices)):
            if i in current:
                continue
            neigh = [j for j in adj[i] if j in disp]
            if not neigh:
                continue
            avg = Vector((0.0, 0.0, 0.0))
            for j in neigh:
                avg += disp[j]
            nxt[i] = (avg / len(neigh)) * falloff
        disp.update(nxt)
        current |= set(nxt)
    stats["blended"] = len(disp) - stats["placed"]
    positions = [v.co + disp.get(i, Vector((0.0, 0.0, 0.0)))
                 for i, v in enumerate(me.vertices)]
    apply_positions(me, positions)
    return stats


def foot_axis(arm: bpy.types.Object, side: str, ref_points=None):
    """The foot's axis: the ankle at t=0, the toe tip at t=1.

    The toe tip is taken from the geometry when it is available: the toe bone
    of the base body points up and forward, so its tail sits several
    centimetres above the actual toes and the axis would be wrong.
    """
    a = arm.data.bones.get(f"足首D.{side}") or arm.data.bones.get(f"足首.{side}")
    if a is None:
        return None
    p0 = arm.matrix_world @ a.head_local
    if ref_points:
        # the model faces -Y, so the toe tip is the point that reaches
        # furthest forward
        tip = min(ref_points, key=lambda p: p.y)
        d = tip - p0
        if d.length > 1e-4:
            return p0, d.normalized(), d.length
    b = arm.data.bones.get(f"つま先.{side}") or arm.data.bones.get(f"足先EX.{side}")
    if b is None:
        return None
    p1 = arm.matrix_world @ b.tail_local
    d = p1 - p0
    if d.length < 1e-6:
        return None
    return p0, d.normalized(), d.length


def fit_paint_layer(garment: bpy.types.Object, tgt_body: bpy.types.Object,
                    tgt_arm: bpy.types.Object, material: str,
                    pairs: list[tuple[str, str]],
                    margin: float = 0.005, percentile: float = 0.92,
                    bins: int = 24, max_factor: float = 1.35
                    ) -> dict[str, Any]:
    """Push a paint layer outwards until it encloses the base body's limb.

    A paint layer (the glove, the shoe, the sock) is the source's own skin with
    the outfit material on it.  It has no thickness, so it has to lie *on* the
    base body's limb - and the base body's limb is thicker than the source's,
    so the layer ends up buried inside it and the base body's skin shows
    through instead.

    Here the layer is pushed outwards around the bone's axis until its cross
    section encloses the base body's limb.  Every bone is handled on its own,
    because a leg is not one straight tube.
    """
    gme = garment.data
    gdom = dominant_bones(garment)
    tme = tgt_body.data
    tdom = dominant_bones(tgt_body)

    layer_faces = [p.index for p in gme.polygons
                   if p.material_index < len(gme.materials) and gme.materials[
                       p.material_index] and gme.materials[
                       p.material_index].name == material]
    if not layer_faces:
        return {"skipped": f"no faces with the material {material}"}
    layer_verts: set[int] = set()
    for fi in layer_faces:
        layer_verts.update(gme.polygons[fi].vertices)

    stats: dict[str, Any] = {"material": material, "faces": len(layer_faces),
                             "bones": {}}
    positions = [v.co.copy() for v in gme.vertices]
    moved = 0
    for layer_bone, ref_bone in pairs:
        b = tgt_arm.data.bones.get(layer_bone)
        rb = tgt_arm.data.bones.get(ref_bone)
        if b is None or rb is None:
            continue
        p0 = tgt_arm.matrix_world @ b.head_local
        p1 = tgt_arm.matrix_world @ b.tail_local
        d = p1 - p0
        if d.length < 1e-5:
            continue
        adir = d.normalized()
        alen = d.length

        # the cross section of a leg is not round, so the radii are compared
        # per direction as well - a factor that only knows the radius leaves
        # the layer inside the limb on the wide side
        ang_bins = 16

        def profile(verts, me, matrix):
            out: dict[tuple[int, int], list[float]] = {}
            for i in verts:
                co = matrix @ me.vertices[i].co
                rel = co - p0
                along = rel.dot(adir)
                radial = rel - adir * along
                r = radial.length
                if r < 1e-6:
                    continue
                ang = int((math.atan2(radial.y, radial.x) + math.pi)
                          / (2 * math.pi) * ang_bins) % ang_bins
                key = (int(round(along / alen * bins)), ang)
                out.setdefault(key, []).append(r)
            return out

        lv = {i for i in layer_verts if gdom[i] == layer_bone}
        rv = {i for i, name in enumerate(tdom) if name == ref_bone}
        if not lv or not rv:
            continue
        sb = profile(lv, gme, garment.matrix_world)
        rb = profile(rv, tme, tgt_body.matrix_world)

        def pick(values: list[float]) -> float:
            if not values:
                return 0.0
            values = sorted(values)
            return values[min(len(values) - 1, int(len(values) * percentile))]

        factor: dict[tuple[int, int], float] = {}
        for k, rs in sb.items():
            want = pick(rb.get(k, [])) + margin
            have = pick(rs)
            factor[k] = min(max_factor, max(1.0, want / have)) if have > 1e-6 else 1.0
        # smooth along the limb, not across the directions
        for _ in range(2):
            for (k, ang), f in list(factor.items()):
                lo = factor.get((k - 1, ang), f)
                hi = factor.get((k + 1, ang), f)
                factor[(k, ang)] = (lo + f * 2 + hi) / 4

        n = 0
        for i in lv:
            co = garment.matrix_world @ gme.vertices[i].co
            rel = co - p0
            along = rel.dot(adir)
            radial = rel - adir * along
            r = radial.length
            if r < 1e-6:
                continue
            ang = int((math.atan2(radial.y, radial.x) + math.pi)
                      / (2 * math.pi) * ang_bins) % ang_bins
            f = factor.get((int(round(along / alen * bins)), ang), 1.0)
            if f <= 1.0005:
                continue
            positions[i] = garment.matrix_world.inverted() @ (p0 + adir * along + radial * f)
            n += 1
        moved += n
        stats["bones"][layer_bone] = {"vertices": len(lv), "moved": n,
                                     "max_factor": round(max(factor.values()), 3)
                                     if factor else 1.0}
    apply_positions(gme, positions)
    stats["moved"] = moved
    return stats


def fit_shoe_to_foot(garment: bpy.types.Object, tgt_body: bpy.types.Object,
                     tgt_arm: bpy.types.Object, side: str,
                     materials=("服", "服+jinshu"),
                     shoe_bones=("足先EX", "足首D", "足D"),
                     ref_bones=("ひざ", "足先EX", "つま先", "足首D",
                                "足親指０", "足親指１", "足人指１", "足人指２",
                                "足中指１", "足中指２", "足薬指１", "足薬指２",
                                "足小指１", "足小指２"),
                     margin: float = 0.008, percentile: float = 0.92,
                     bins: int = 48, max_factor: float = 1.3) -> dict[str, Any]:
    """Make the shoe enclose the base body's foot.

    The shoe is the source's own foot surface, so it has the source's shape.
    The base body's foot is bigger and has five separate toes, and they stick
    out of the shoe.  Here the shoe is pushed outwards around the foot's axis
    until its cross section encloses the base body's leg and foot.

    The shoe is picked by material *and* by the foot bones, never by the
    bone alone: a skirt hem is regularly bound to a foot bone to keep it out
    of the legs, and that hem must not be blown up together with the shoe.

    The factor is capped: where the shoe tapers to a point and the base body
    has a wide toe, the ratio explodes and the shoe would balloon.
    """
    gme = garment.data
    gdom = dominant_bones(garment)
    side_tag = "." + side
    shoe_bones = {f"{b}{side_tag}" for b in shoe_bones}

    shoe_faces = []
    for p in gme.polygons:
        verts = list(p.vertices)
        if not verts:
            continue
        mi = p.material_index
        name = gme.materials[mi].name if mi < len(gme.materials) and gme.materials[mi] else ""
        if name not in materials:
            continue
        hits = sum(1 for v in verts if gdom[v] in shoe_bones)
        if hits >= len(verts) * 0.5:
            shoe_faces.append(p.index)
    shoe_verts: set[int] = set()
    for fi in shoe_faces:
        shoe_verts.update(gme.polygons[fi].vertices)
    if not shoe_verts:
        return {"skipped": "no shoe faces found"}

    # the base body's leg and foot: the cross section the shoe has to enclose
    tme = tgt_body.data
    tdom = dominant_bones(tgt_body)
    ref_bones = {f"{b}{side_tag}" for b in ref_bones}
    ref_verts = set()
    for p in tme.polygons:
        verts = list(p.vertices)
        if verts and any(tdom[v] in ref_bones for v in verts):
            ref_verts.update(verts)
    if not ref_verts:
        return {"skipped": "no leg or foot on the base body"}

    ref_points = [tgt_body.matrix_world @ tme.vertices[i].co for i in ref_verts]
    axis = foot_axis(tgt_arm, side, ref_points)
    if axis is None:
        return {"skipped": f"no foot axis for {side}"}
    p0, adir, alen = axis

    def profile(verts, me, matrix):
        out: dict[int, list[float]] = {}
        for i in verts:
            co = matrix @ me.vertices[i].co
            rel = co - p0
            along = rel.dot(adir)
            t = along / alen
            r = (rel - adir * along).length
            out.setdefault(int(round(t * bins)), []).append(r)
        return out

    sb = profile(shoe_verts, gme, garment.matrix_world)
    rb = profile(ref_verts, tme, tgt_body.matrix_world)

    def pick(values: list[float]) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        return values[min(len(values) - 1, int(len(values) * percentile))]

    factor: dict[int, float] = {}
    for b, rs in sb.items():
        want = pick(rb.get(b, [])) + margin
        have = pick(rs)
        factor[b] = min(max_factor, max(1.0, want / have)) if have > 1e-6 else 1.0
    # smooth the factors, a step would crease the shoe
    for _ in range(2):
        for b in list(factor):
            lo = factor.get(b - 1, factor[b])
            hi = factor.get(b + 1, factor[b])
            factor[b] = (lo + factor[b] * 2 + hi) / 4

    positions = [v.co.copy() for v in gme.vertices]
    moved = 0
    for i in shoe_verts:
        co = gme.vertices[i].co
        rel = garment.matrix_world @ co - p0
        along = rel.dot(adir)
        t = along / alen
        radial = rel - adir * along
        r = radial.length
        if r < 1e-6:
            continue
        b = int(round(t * bins))
        f = factor.get(b, 1.0)
        if f <= 1.0005:
            continue
        new_rel = adir * along + radial * f
        positions[i] = garment.matrix_world.inverted() @ (p0 + new_rel)
        moved += 1
    apply_positions(gme, positions)
    return {"shoe_faces": len(shoe_faces), "shoe_vertices": len(shoe_verts),
            "reference_vertices": len(ref_verts), "moved": moved,
            "max_factor": round(max(factor.values()), 3) if factor else 1.0,
            "side": side}


def subdivide_triangles(me: bpy.types.Mesh, face_ids: list[int],
                        uv_name: str = "UVMap") -> int:
    """Split the given faces into smaller ones and keep every attribute.

    The layer has to get dense enough to wrap a leg, and it has to keep its
    rig, its texture and its morphs while it does.

    Three things are easy to get wrong here, and all of them are silent:

    * A new vertex in the middle of an edge that a face *outside* the
      selection still uses is a T-junction.  The two sides of that edge stop
      being connected, and the surface tears as soon as the weights or the
      morphs differ across it.  So an edge that a face outside the selection
      shares is left alone - the faces next to it are split from a new
      vertex in their middle instead of from a midpoint on that edge.
    * Only one UV layer would be interpolated and the morphs would be
      dropped, so a model with a shape key would export broken.
    * A new vertex starts at (0, 0, 0) in every shape key, and the shape
      layers hold absolute positions, so every one of them has to be written
      back by hand.

    bmesh.ops.subdivide_edges does not cut the triangles (it only puts
    midpoints on the edges, the surface stays as coarse as it was), which is
    why the faces are split by hand here.
    """
    import bmesh

    if not face_ids:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    uv_layers = list(bm.loops.layers.uv)
    deform = bm.verts.layers.deform.active
    shape_layers = list(bm.verts.layers.shape)

    sel_ids = [i for i in face_ids if 0 <= i < len(bm.faces)]
    if not sel_ids:
        bm.free()
        return 0
    sel_set = set(sel_ids)

    def edge_key(a: int, b: int) -> tuple[int, int]:
        return (a, b) if a < b else (b, a)

    # ---- capture everything before the mesh is touched --------------------
    def vert_data(v):
        d = {"co": v.co.copy()}
        if deform is not None:
            d["w"] = dict(v[deform].items())
        if shape_layers:
            # a bmesh shape layer holds the *absolute* position of the vertex
            # in that shape key
            d["s"] = {lay.name: Vector(v[lay]) for lay in shape_layers}
        return d

    face_info: list[dict[str, Any]] = []
    edge_use: dict[tuple[int, int], int] = {}
    for fi in sel_ids:
        f = bm.faces[fi]
        corners = [v.index for v in f.verts]
        uvs = {lay.name: [Vector(l[lay].uv) for l in f.loops] for lay in uv_layers}
        face_info.append({"corners": corners, "uvs": uvs,
                          "material": f.material_index, "smooth": f.smooth})
        n = len(corners)
        for k in range(n):
            key = edge_key(corners[k], corners[(k + 1) % n])
            edge_use[key] = edge_use.get(key, 0) + 1

    involved: set[int] = set()
    for info in face_info:
        involved.update(info["corners"])
    src = {i: vert_data(bm.verts[i]) for i in involved}

    # ---- the edges a face outside the selection shares with us -----------
    # Those keep their length: a midpoint on them would be a T-junction.
    outside_users: dict[tuple[int, int], int] = {}
    for e in bm.edges:
        key = edge_key(e.verts[0].index, e.verts[1].index)
        if key not in edge_use:
            continue
        outside = sum(1 for f in e.link_faces if f.index not in sel_set)
        if outside:
            outside_users[key] = outside
    keep_edge = {k for k, n in outside_users.items() if edge_use[k] == 1}

    # ---- one midpoint per edge, shared by the faces that use it ----------
    mid_co: dict[tuple[int, int], Vector] = {}
    mid_w: dict[tuple[int, int], dict[str, float]] = {}
    mid_s: dict[tuple[int, int], dict[str, Vector]] = {}
    for key in edge_use:
        if key in keep_edge:
            continue
        a, b = src[key[0]], src[key[1]]
        mid_co[key] = (a["co"] + b["co"]) * 0.5
        if deform is not None:
            w: dict[str, float] = {}
            for g in set(a["w"]) | set(b["w"]):
                w[g] = 0.5 * a["w"].get(g, 0.0) + 0.5 * b["w"].get(g, 0.0)
            mid_w[key] = w
        if shape_layers:
            s: dict[str, Vector] = {}
            for lay in shape_layers:
                s[lay.name] = (a["s"][lay.name] + b["s"][lay.name]) * 0.5
            mid_s[key] = s

    # ---- create the midpoints --------------------------------------------
    mid_index: dict[tuple[int, int], int] = {}
    for key, co in mid_co.items():
        v = bm.verts.new(co)
        if deform is not None:
            for g, val in mid_w[key].items():
                v[deform][g] = val
        for lay in shape_layers:
            v[lay] = mid_s[key][lay.name]
        mid_index[key] = len(bm.verts) - 1
    bm.verts.ensure_lookup_table()

    # ---- the centre of every face that cannot be split into four --------
    # They are all created up front: adding a vertex invalidates the lookup
    # table that the face creation below relies on.
    for info in face_info:
        corners = info["corners"]
        n = len(corners)
        keys = [edge_key(corners[k], corners[(k + 1) % n]) for k in range(n)]
        if n == 3 and all(k in mid_index for k in keys):
            continue
        centre = bm.verts.new(Vector((0.0, 0.0, 0.0)))
        acc = Vector((0.0, 0.0, 0.0))
        for ci in corners:
            acc += src[ci]["co"]
        centre.co = acc / len(corners)
        if deform is not None:
            wsum: dict[str, float] = {}
            for ci in corners:
                for g, val in src[ci]["w"].items():
                    wsum[g] = wsum.get(g, 0.0) + val / len(corners)
            for g, val in wsum.items():
                centre[deform][g] = val
        for lay in shape_layers:
            acc = Vector((0.0, 0.0, 0.0))
            for ci in corners:
                acc += src[ci]["s"][lay.name]
            centre[lay] = acc / len(corners)
        info["centre"] = centre
    bm.verts.ensure_lookup_table()

    # ---- the new faces ----------------------------------------------------
    new_faces: list[Any] = []
    for info in face_info:
        corners = info["corners"]
        uvs = info["uvs"]
        n = len(corners)
        if n < 3:
            continue
        keys = [edge_key(corners[k], corners[(k + 1) % n]) for k in range(n)]
        if n == 3 and all(k in mid_index for k in keys):
            # the plain 1 -> 4 split
            a, b, c = corners
            ab = mid_index[keys[0]]
            bc = mid_index[keys[1]]
            ca = mid_index[keys[2]]
            plan = (
                ((a, ab, ca),
                 lambda u: (u[0], (u[0] + u[1]) * 0.5, (u[2] + u[0]) * 0.5)),
                ((ab, b, bc),
                 lambda u: ((u[0] + u[1]) * 0.5, u[1], (u[1] + u[2]) * 0.5)),
                ((ca, bc, c),
                 lambda u: ((u[2] + u[0]) * 0.5, (u[1] + u[2]) * 0.5, u[2])),
                ((ab, bc, ca),
                 lambda u: ((u[0] + u[1]) * 0.5, (u[1] + u[2]) * 0.5,
                            (u[2] + u[0]) * 0.5)),
            )
            for tri, pick in plan:
                nf = bm.faces.new([bm.verts[i] for i in tri])
                nf.material_index = info["material"]
                nf.smooth = info["smooth"]
                for lay in uv_layers:
                    values = pick(uvs[lay.name])
                    for loop, value in zip(nf.loops, values):
                        loop[lay].uv = value
                new_faces.append(nf)
            continue
        # a fan from a new vertex in the middle.  The boundary of the face
        # keeps the edges that a face outside the selection shares, so the
        # two sides of those edges stay connected.
        centre = info["centre"]
        seq: list[int] = []
        for k in range(n):
            seq.append(corners[k])
            if keys[k] in mid_index:
                seq.append(mid_index[keys[k]])
        seq_uv: dict[str, list[Vector]] = {}
        for lay in uv_layers:
            u = uvs[lay.name]
            vals: list[Vector] = []
            for k in range(n):
                vals.append(u[k])
                if keys[k] in mid_index:
                    vals.append((u[k] + u[(k + 1) % n]) * 0.5)
            seq_uv[lay.name] = vals
        m = len(seq)
        for k in range(m):
            i0, i1 = seq[k], seq[(k + 1) % m]
            nf = bm.faces.new([bm.verts[i0], bm.verts[i1], centre])
            nf.material_index = info["material"]
            nf.smooth = info["smooth"]
            for lay in uv_layers:
                vals = seq_uv[lay.name]
                u0 = vals[k]
                u1 = vals[(k + 1) % m]
                nf.loops[0][lay].uv = u0
                nf.loops[1][lay].uv = u1
                nf.loops[2][lay].uv = (u0 + u1) * 0.5
            new_faces.append(nf)

    # ---- the old faces go away -------------------------------------------
    bm.faces.ensure_lookup_table()
    old = [bm.faces[fi] for fi in sel_ids]
    bmesh.ops.delete(bm, geom=old, context='FACES')
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(new_faces)


def project_layer_on_limb(garment: bpy.types.Object, tgt_body: bpy.types.Object,
                           tgt_arm: bpy.types.Object, side: str, material: str,
                           ref_bones: tuple[str, ...],
                           axis_bones: tuple[str, str] = ("足", "ひざ"),
                           margin: float = 0.004, subdivide_levels: int = 2,
                           max_dist: float = 0.12, fade_rings: int = 2,
                           knee_band: float = 0.05,
                           body_bones: set[str] | None = None,
                           target_weights: bool = False
                           ) -> dict[str, Any]:
    """Lay a paint layer onto the base body's limb.

    A paint layer (the sock) is the source's own skin painted with the outfit
    material.  It has no thickness of its own, so it has to lie *on* the base
    body's limb - and the base body's limb is thicker than the source's, so
    the layer ends up buried inside it and the base body's skin shows
    through.

    The layer is subdivided first (a few hundred vertices cannot wrap a leg
    without the surface cutting through it), then every vertex is pushed out
    along the limb's axis onto the base body's surface plus a margin.  A
    nearest point search would not do: the layer is *inside* the limb, and
    the nearest surface point is then in an arbitrary direction, which folds
    the layer up.  The radial keeps the angle and only moves the radius.

    A leg bends at the knee, so it has two axes: the thigh's and the shin's.
    Switching between them at a fixed height makes the layer bunch up at the
    knee, so the two are blended over a band around it.

    The movement fades out at the layer's cuff, so it does not tear away from
    the rest of the outfit.
    """
    gme = garment.data
    tme = tgt_body.data
    tdom = dominant_bones(tgt_body)
    side_tag = "." + side

    def layer_faces() -> list[int]:
        """The layer's faces on this side - collected again every time.

        Subdividing renumbers the faces, so an index list from before the
        subdivision points at the wrong faces.
        """
        dom = dominant_bones(garment)
        out = []
        for p in gme.polygons:
            mi = p.material_index
            if mi >= len(gme.materials) or not gme.materials[mi]:
                continue
            if gme.materials[mi].name != material:
                continue
            verts = list(p.vertices)
            if verts and sum(1 for v in verts if dom[v].endswith(side_tag)) \
                    >= len(verts) * 0.5:
                out.append(p.index)
        return out

    if not layer_faces():
        return {"skipped": f"no {material} faces on {side}"}

    # the base body's limb: the skin the leg bones drive
    ref = {f"{b}.{side}" for b in ref_bones}
    body_faces = []
    for p in tme.polygons:
        verts = list(p.vertices)
        if verts and any(tdom[v] in ref for v in verts):
            body_faces.append(p.index)
    if not body_faces:
        return {"skipped": "the base body has no leg to lay the layer on"}
    verts = [tme.vertices[i].co.copy() for i in range(len(tme.vertices))]
    bvh = BVHTree.FromPolygons(verts,
                                [[i for i in tme.polygons[fi].vertices]
                                 for fi in body_faces],
                                all_triangles=False, epsilon=0.0)

    # the limb's axis: every bone has its own, because a leg bends at the
    # knee.  The hip is a centre bone in MMD, so the side suffix is
    # optional.
    def find_bone(name: str):
        b = tgt_arm.data.bones.get(f"{name}.{side}")
        if b is None:
            b = tgt_arm.data.bones.get(name)
        return b

    def bone_axis(name: str):
        b = find_bone(name)
        if b is None:
            return None
        head = tgt_arm.matrix_world @ b.head_local
        tail = tgt_arm.matrix_world @ b.tail_local
        d = tail - head
        if d.length < 1e-6:
            return None
        return head, d.normalized()

    # The control bones (足, ひざ) follow the limb; the deformation bones
    # (足D, ひざD) are short helpers - ひざD points from the knee *upwards*,
    # and an axis built on it puts the sock's calf nowhere near the leg.
    thigh_axis = bone_axis(axis_bones[0])
    shin_axis = bone_axis(axis_bones[1])
    if thigh_axis is None or shin_axis is None:
        return {"skipped": f"no limb axes on {side}",
                "axes": list(axis_bones)}
    knee = find_bone(axis_bones[1])
    knee_z = (tgt_arm.matrix_world @ knee.head_local).z if knee else 0.0

    def knee_weight(z: float) -> float:
        """0 = the thigh's axis, 1 = the shin's, smooth in between."""
        if z >= knee_z + knee_band:
            return 0.0
        if z <= knee_z - knee_band:
            return 1.0
        t = (knee_z + knee_band - z) / (2.0 * knee_band)
        return t * t * (3.0 - 2.0 * t)

    def axis_hit(axis, co: Vector):
        """Where the layer's point lands on the base body's surface."""
        origin0, dir0 = axis
        rel = co - origin0
        along = rel.dot(dir0)
        radial = rel - dir0 * along
        if radial.length < 1e-6:
            return None
        direction = radial.normalized()
        origin = origin0 + dir0 * along
        hit, nrm, _idx, _dist = bvh.ray_cast(origin, direction, max_dist)
        if hit is None or nrm.length < 1e-6:
            return None
        return hit + nrm * margin

    added = 0
    for _ in range(subdivide_levels):
        own = layer_faces()
        if not own:
            break
        added += subdivide_triangles(gme, own)
    own = layer_faces()
    if not own:
        return {"skipped": f"no {material} faces on {side} after the subdivision"}

    layer_verts = set()
    for fi in own:
        layer_verts.update(gme.polygons[fi].vertices)

    # the bone every layer vertex follows - kept for the report
    dom = dominant_bones(garment)

    # the border of the layer: the vertices that belong to only one of its
    # faces.  They keep their place, everything inside moves.
    edge_use: dict[tuple[int, int], int] = {}
    for fi in own:
        vs = list(gme.polygons[fi].vertices)
        for k in range(len(vs)):
            a, b = vs[k], vs[(k + 1) % len(vs)]
            key = (min(a, b), max(a, b))
            edge_use[key] = edge_use.get(key, 0) + 1
    border = set()
    for key, n in edge_use.items():
        if n == 1:
            border.update(key)
    # Only the cuff at the top of the layer keeps its place.  The lower
    # border sits inside the boot, and holding it there is what left the
    # ankle bare.
    zs = [gme.vertices[i].co.z for i in layer_verts]
    z_lo, z_hi = (min(zs), max(zs)) if zs else (0.0, 0.0)
    top_cut = z_hi - 0.25 * (z_hi - z_lo)
    top_border = {i for i in border if gme.vertices[i].co.z > top_cut}
    depth: dict[int, int] = {i: 0 for i in top_border}
    for _ in range(fade_rings):
        nxt = {}
        for i in list(depth):
            for e in gme.edges:
                if e.vertices[0] == i or e.vertices[1] == i:
                    other = e.vertices[1] if e.vertices[0] == i else e.vertices[0]
                    if other not in depth and other in layer_verts:
                        nxt[other] = depth[i] + 1
        depth.update(nxt)
    for i in layer_verts:
        depth.setdefault(i, fade_rings + 1)

    positions = [v.co.copy() for v in gme.vertices]
    moved = 0
    missed = 0
    max_disp = 0.0
    knee_disp = 0.0
    for i in layer_verts:
        v = gme.vertices[i]
        rings = depth.get(i, fade_rings + 1)
        w = min(1.0, rings / max(1, fade_rings))
        if w <= 0.0:
            continue
        kw = knee_weight(v.co.z)
        acc = Vector((0.0, 0.0, 0.0))
        weight_sum = 0.0
        if kw < 1.0:
            hit = axis_hit(thigh_axis, v.co)
            if hit is not None:
                acc += hit * (1.0 - kw)
                weight_sum += 1.0 - kw
        if kw > 0.0:
            hit = axis_hit(shin_axis, v.co)
            if hit is not None:
                acc += hit * kw
                weight_sum += kw
        if weight_sum <= 1e-6:
            missed += 1
            continue
        target = acc / weight_sum
        positions[i] = v.co + (target - v.co) * w
        moved += 1
        disp = (target - v.co).length * w
        max_disp = max(max_disp, disp)
        if abs(v.co.z - knee_z) <= knee_band:
            knee_disp = max(knee_disp, disp)
    # The layer ends above the boot, and the base body's leg is thicker than
    # the source's, so a strip of bare skin shows in between.  Carrying the
    # lower border down the limb was tried and is worse: the stretched hem
    # pokes out of the boot's collar as spikes.
    apply_positions(gme, positions)

    stats = {"material": material, "side": side,
             "axes": [axis_bones[0], axis_bones[1]],
             "knee_z": round(knee_z, 4),
             "knee_band": knee_band,
             "faces": len(own), "vertices": len(layer_verts),
             "subdivided_faces": added, "moved": moved,
             "missed_rays": missed,
             "max_displacement": round(max_disp, 5),
             "knee_max_displacement": round(knee_disp, 5),
             "hem_z": [round(z_lo, 4), round(z_hi, 4)],
             "border_vertices": len(border)}

    # The layer keeps the *source*'s weights, so it follows the source's
    # leg and not the base body's.  A paint layer has no bones of its own,
    # so it can take the base body's skin weights outright - unless it
    # carries a bone that is not a body bone, and that one has to survive.
    if target_weights and body_bones:
        gnames = [vg.name for vg in garment.vertex_groups]
        foreign = set()
        for i in layer_verts:
            for g in gme.vertices[i].groups:
                name = gnames[g.group]
                if name not in body_bones:
                    foreign.add(name)
        if foreign:
            stats["target_weights"] = "skipped"
            stats["foreign_bones"] = sorted(foreign)
        else:
            tightness = [0.0] * len(gme.vertices)
            for i in layer_verts:
                tightness[i] = 1.0
            stats["target_weights"] = transfer_target_weights(
                garment, tgt_body, body_bones, tightness, blend=1.0,
                max_dist=0.05, domains=False)
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
                     max_push: float = 0.012,
                     lay_on_surface: tuple[str, ...] = (),
                     lay_on_bones: dict[str, tuple[str, ...]] | None = None
                     ) -> dict[str, Any]:
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
    gdom = dominant_bones(garment)
    lay_on_bones = lay_on_bones or {}
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
        # outside the surface and not touching it -> the piece is fine, unless
        # this region has to be laid onto the surface as a whole (the shoe
        # floats above the foot because the two models anchor it to different
        # bones, and only its shape is right)
        # The shoe is not a shell around the foot: the part the source's foot
        # axis bone drives is the foot's own surface painted with the outfit
        # material, and that part has to be laid onto the base body's foot.
        # The boot above it keeps its own shape.
        painted = (key in lay_on_surface
                   and gdom[i].split(".")[0] in
                   {b.split(".")[0] for b in lay_on_bones.get(key, ())})
        if not painted and (v.co - loc).dot(nrm) >= 0.0 and dist > near_dist:
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

    The pmx importer leaves `blend_method` at 'HASHED' on every material -
    that is the opaque default in Blender 5.x and says nothing about the
    material being see through.  Only 'BLEND' does, and that is what mmd_tools
    sets for a material with the semi transparent draw mode.  Reading
    'HASHED' as transparent made the whole body mask a no operation.
    """
    if mat is None:
        return True
    try:
        mmd = mat.mmd_material
        if getattr(mmd, "alpha", 1.0) < 0.99:
            return True
    except Exception:
        pass
    try:
        if mat.blend_method == 'BLEND':
            return True
    except Exception:
        pass
    try:
        if getattr(mat, "surface_render_method", "") == 'BLENDED':
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
        # Laying the shoe onto the foot surface as a whole was tried and
        # reverted: the shoe is not a shell around the foot, it is the foot's
        # surface painted plus the boot above it, and projecting everything
        # flattens the boot and tears the metal trim apart.  The shoe has to
        # be anchored to the foot the way the source anchors it - that needs
        # the foot bones mapped by anatomy, not by name.
        "limb_lay_on_surface": [],
        "scale_limbs": True,
        # The shoe is the source's own toe surface and carries a few hundred
        # vertices for the whole foot, while the base body's foot has
        # thousands.  Fitting that coarse surface cuts the base body's toes
        # through it - the resolution is the problem, not the position.  So
        # the shoe is subdivided first and then laid on the foot.
        # Both steps are experimental: the subdivision does not cut the
        # triangles yet and the projection treats the shoe like skin, which
        # breaks the toe cap and the metal trim (see docs/REVIEW.md).
        # Off by default until the semantic parts are separated.
        "subdivide_shoe": 0,
        "lay_shoe_on_foot": False,
        # The shoe is the source's foot surface: it has the source's shape,
        # the base body's foot is bigger.  Pushing the shoe outwards around
        # the foot's axis helps a little but does not close the toe cap, and
        # the boot's shaft is already torn open - this is the "shoe last"
        # work of docs/REVIEW.md (3.3) and stays off until the shoe is split
        # into its parts.
        "fit_shoe_radius": False,
        # A paint layer (the sock) is the source's own skin with the outfit
        # material on it.  It has no thickness and the base body's limb is
        # thicker than the source's, so the layer ends up buried inside the
        # limb and the base body's skin shows through.  This pushes the layer
        # out until its cross section encloses the limb.
        # Off by default: it needs the layer split from the rest of the outfit
        # first, and it does not close the front of the limb yet.
        "fit_paint_layers": [],
        # A paint layer (the sock) is the source's own skin painted with the
        # outfit material.  It has no thickness and the base body's limb is
        # thicker, so the layer ends up buried inside it.
        # Laying it on the base body's surface is the right idea, but a single
        # axis from the hip to the ankle does not fit a leg that bends at the
        # knee: the layer bunches up there.  The fix is the target derived
        # patch of docs/REVIEW2.md (3.2) - copy the base body's skin patch
        # and move the source's texture onto it.  Off until that exists.
        "project_layers": [
            {"material": "腿", "margin": 0.004, "subdivide": 2,
             "bones": ("ひざD", "足D", "下半身", "足首D", "足先EX"),
             # the thigh's and the shin's control bone - the deformation
             # bones (ひざD) point upwards and make an axis that misses
             # the leg entirely
             "axis": ("足", "ひざ"),
             # the layer takes the base body's skin weights, so it follows
             # the base body's leg and not the source's
             "target_weights": True},
        ],
        "shoe_margin": 0.004,
        "shoe_blend_rings": 3,
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
        # keep the weight search inside the digit the vertex belongs to
        "weight_domains": True,
        # the hand is tight by construction - transfer its weights even when
        # the geometric tightness measure says nothing
        "weight_limbs": True,
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

    # ---- the shoe has to be dense enough to wrap the base body's toes ----
    shoe_stats: dict[str, Any] = {}
    if cloth and cfg["fit"].get("subdivide_shoe"):
        shoe_stats["subdivide"] = subdivide_shoe(
            cloth[0], levels=int(cfg["fit"]["subdivide_shoe"]))
        snapshot("stage2b_subdivided")

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
    if cloth and cfg["fit"].get("use_target_weights", False):
        # the hands are tight by construction, but the geometric tightness
        # measure cannot tell the fingers apart - they get their own gate
        hands = [bool(r) and r.startswith("hand") for r in limb_regions(cloth[0])]
        reweight_stats = transfer_target_weights(
            cloth[0], tgt_body_meshes[0], body_bones, tightness,
            blend=cfg["fit"].get("target_weight_blend", 0.8),
            domains=cfg["fit"].get("weight_domains", True),
            always_regions=hands if cfg["fit"].get("weight_limbs", True) else None)

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
            max_push=cfg["fit"].get("limb_max_push", 0.012),
            lay_on_surface=tuple(cfg["fit"].get("limb_lay_on_surface",
                                               ("foot_L", "foot_R"))),
            lay_on_bones={"foot_L": ("足先EX.L",), "foot_R": ("足先EX.R",)})
        limb_fit_stats["forward_scale"] = forward

    # The shoe lies on the base body's foot, not around it: place it there.
    # This runs last, so the general limb fit cannot pull it off again.
    if cloth and cfg["fit"].get("lay_shoe_on_foot", True):
        for side in ("L", "R"):
            fbvh = foot_bvh(tgt_body_meshes, tgt_arm, side)
            if fbvh is None:
                continue
            shoe_stats[side] = lay_shoe_on_foot(
                cloth[0], fbvh, bones=(f"足先EX.{side}",),
                margin=cfg["fit"].get("shoe_margin", 0.004),
                blend_rings=int(cfg["fit"].get("shoe_blend_rings", 3)))

    if cloth and cfg["fit"].get("fit_shoe_radius", False):
        for side in ("L", "R"):
            shoe_stats[f"radius_{side}"] = fit_shoe_to_foot(
                cloth[0], tgt_body_meshes[0], tgt_arm, side,
                margin=cfg["fit"].get("shoe_radius_margin", 0.008))

    for spec in cfg["fit"].get("fit_paint_layers", []):
        pairs = [tuple(p) for p in spec.get("pairs", [])]
        if not pairs:
            continue
        shoe_stats[f"paint_{spec['material']}"] = fit_paint_layer(
            cloth[0], tgt_body_meshes[0], tgt_arm, spec["material"], pairs,
            margin=cfg["fit"].get("paint_margin", 0.005),
            max_factor=cfg["fit"].get("paint_max_factor", 1.35))

    for spec in cfg["fit"].get("project_layers", []):
        bones = tuple(spec.get("bones", ()))
        if not bones:
            continue
        for side in ("L", "R"):
            shoe_stats[f"project_{spec['material']}_{side}"] = (
                project_layer_on_limb(
                    cloth[0], tgt_body_meshes[0], tgt_arm, side, spec["material"], bones,
                    axis_bones=tuple(spec.get("axis", ("足", "ひざ"))),
                    margin=spec.get("margin", 0.004),
                    subdivide_levels=int(spec.get("subdivide", 2)),
                    knee_band=float(spec.get("knee_band", 0.05)),
                    body_bones=body_bones,
                    target_weights=bool(spec.get("target_weights", True))))

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
        z_limit = neck_height(tgt_arm)
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
            # 刻晴's glove, shoe and sock are her own skin painted with the
            # outfit material: there is no separate skin face under them, so
            # the coverage of those parts comes out empty and the base body's
            # foot stays visible inside the shoe.  Measuring it directly on
            # the base body finds them.
            direct, covered_points = mask_by_garment(
                tgt_body_meshes[0], cloth[0], garment_bvh,
                max_dist=cfg["body_mask"].get("cover_dist", 0.015))
            direct = [fi for fi in direct
                      if (tgt_body_meshes[0].matrix_world
                          @ tgt_body_meshes[0].data.polygons[fi].center).z
                      <= z_limit]
            mask_stats["covered_points"] = covered_points
            mask_stats["direct_faces"] = len(direct)
            mask_stats["source_faces"] = len(to_delete)
            to_delete = sorted(set(to_delete) | set(direct))
            mask_stats["method"] = "source+direct"
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
                "limb_ends": limb_stats, "shoe": shoe_stats,
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
