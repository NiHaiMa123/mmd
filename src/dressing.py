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
    """D = M_target @ M_source^-1 for every mapped bone."""
    S = {b.name: b.matrix_local.copy() for b in src_arm.data.bones}
    T = {b.name: b.matrix_local.copy() for b in tgt_arm.data.bones}
    out = {}
    for s, t in mapping.items():
        if s in S and t in T:
            out[s] = T[t] @ S[s].inverted()
    return out


def garment_deltas(src_arm: bpy.types.Object, garment_bones: list[str],
                   deltas: dict[str, Matrix]) -> dict[str, Matrix]:
    """Delta for a garment-only bone = the delta of its parent.

    A garment bone rides on its parent, so it inherits the parent's mapping.
    """
    S = {b.name: b.matrix_local.copy() for b in src_arm.data.bones}
    resolved: dict[str, Matrix] = {}

    def resolve(name: str) -> Matrix:
        if name in resolved:
            return resolved[name]
        if name in deltas:
            resolved[name] = deltas[name]
            return resolved[name]
        bone = src_arm.data.bones.get(name)
        if bone is None or bone.parent is None:
            resolved[name] = Matrix.Identity(4)
            return resolved[name]
        d = resolve(bone.parent.name)
        resolved[name] = d
        return d

    out = {}
    for name in garment_bones:
        d = resolve(name)
        resolved[name] = d
        out[name] = d
    return out


def garment_bone_specs(src_arm: bpy.types.Object, garment_bones: list[str],
                       deltas: dict[str, Matrix]) -> list[dict[str, Any]]:
    """Head / tail / parent / roll direction for every garment-only bone."""
    S = {b.name: b.matrix_local.copy() for b in src_arm.data.bones}
    specs = []
    for name in garment_bones:
        bone = src_arm.data.bones.get(name)
        if bone is None:
            continue
        parent = bone.parent.name if bone.parent else None
        d = deltas.get(name)
        if d is None or parent is None:
            continue
        m = d @ S[name]
        head = m.translation.copy()
        tail = head + m.to_3x3() @ (bone.tail_local - bone.head_local)
        specs.append({
            "name": name,
            "parent": parent,
            "head": head,
            "tail": tail,
            "roll_axis": (m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized(),
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
                v.co = (rot @ v.co + trans) / wsum
            else:
                v.co = rot @ v.co + trans
            weighted[v.index] = wsum

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
            if names[g.group] in body_bones:
                wb = max(wb, g.weight)
            else:
                wg = max(wg, g.weight)
        # smooth transition around the point where the two compete
        t = (wb - wg) / 0.25
        t = max(0.0, min(1.0, t + 0.5))
        out.append(t * t * (3.0 - 2.0 * t))
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
    for v in me.vertices:
        c = corrections[v.index]
        v.co = v.co + Vector(c)

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


def source_coverage(src_body: bpy.types.Object, garment_bvh: BVHTree,
                    face_indices: list[int], max_dist: float = 0.02,
                    margin: int = 1) -> dict[int, bool]:
    """Which source body vertices sit under the clothes.

    The test is per *vertex*: a source leg can be a single huge face, and a
    per face decision would either hide the whole leg or none of it.

    A vertex is covered when the clothes are close to it and lie on the
    outside of the body - the same local reasoning the motion check uses.

    `margin` erodes the covered area by that many vertex rings, so the skin
    stays visible at the openings (collar, cuffs, hem) where the clothes do
    not really seal.
    """
    me = src_body.data
    mw = src_body.matrix_world
    verts = set()
    for fi in face_indices:
        verts.update(me.polygons[fi].vertices)

    covered: dict[int, bool] = {}
    for i in verts:
        v = me.vertices[i]
        co = mw @ v.co
        n = (mw.to_3x3() @ v.normal).normalized()
        loc, _nrm, _idx, dist = garment_bvh.find_nearest(co)
        if loc is None:
            covered[i] = False
            continue
        side = (loc - co).dot(n)
        covered[i] = (dist <= max_dist and side > 0.0)

    if margin > 0:
        adj: dict[int, set[int]] = {i: set() for i in verts}
        for e in me.edges:
            a, b = e.vertices
            if a in adj and b in adj:
                adj[a].add(b)
                adj[b].add(a)
        for _ in range(margin):
            covered = {i: (covered[i] and
                           all(covered.get(n, False) for n in adj[i]))
                       for i in verts}
    return covered


def transfer_coverage(target_body: bpy.types.Object, src_body: bpy.types.Object,
                      covered: dict[int, bool], max_dist: float = 0.04,
                      z_limit: float = float("inf")) -> list[int]:
    """Map the source coverage onto the target body; return faces to delete.

    The lookup happens per vertex, so the boundary of the hidden area follows
    the clothes instead of jumping along the source's coarse faces.
    """
    from mathutils.kdtree import KDTree

    me = src_body.data
    mw = src_body.matrix_world
    kd = KDTree(len(covered))
    for i in covered:
        kd.insert(mw @ me.vertices[i].co, i)
    kd.balance()

    tme = target_body.data
    tmw = target_body.matrix_world
    delete = []
    for poly in tme.polygons:
        center = tmw @ poly.center
        if center.z > z_limit:
            continue
        _co, index, dist = kd.find(center)
        if index is None or dist > max_dist:
            continue
        if covered.get(index, False):
            delete.append(poly.index)
    return delete


_CONTAIN_DIRS = (
    Vector((0.0, 0.0, 1.0)), Vector((0.0, 0.0, -1.0)),
    Vector((1.0, 0.0, 0.0)), Vector((-1.0, 0.0, 0.0)),
    Vector((0.0, 1.0, 0.0)), Vector((0.0, -1.0, 0.0)),
)


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
        "max_pull": 0.05,
        "max_fit_dist": 0.05,
    },
    "body_mask": {
        "enabled": True,
        "max_dist": 0.08,
        "hair_max_dist": 0.04,
        "hair": True,
        "margin": 1,
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
    tightness = body_bone_tightness(cloth[0], body_bones) if cloth else []
    fit_stats = fit_to_body(cloth[0], tgt_bvh, tightness,
                            offset=cfg["fit"]["offset"],
                            strength=cfg["fit"]["strength"],
                            max_pull=cfg["fit"]["max_pull"],
                            max_fit_dist=cfg["fit"]["max_fit_dist"]) if cloth else {}

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
    mask_stats = {"enabled": cfg["body_mask"]["enabled"], "deleted_faces": 0}
    if cfg["body_mask"]["enabled"] and cloth:
        garment_bvh = build_bvh(cloth[0])
        # the source body: everything that is neither hair, face nor the
        # clothing itself - that is the skin the clothes may cover
        cloth_face_set = set(cloth_faces.get(src_body.name, []))
        src_skin_faces = [fi for fi in body_faces(src_body, skip_hair=True,
                                                   skip_face=True)
                          if fi not in cloth_face_set]
        coverage = source_coverage(src_body, garment_bvh, src_skin_faces,
                                   margin=cfg["body_mask"].get("margin", 1))
        to_delete = transfer_coverage(tgt_body_meshes[0], src_body, coverage,
                                      max_dist=cfg["body_mask"]["max_dist"],
                                      z_limit=neck_height(tgt_arm))
        mask_stats["source_covered_faces"] = sum(1 for v in coverage.values() if v)
        mask_stats["deleted_faces"] = delete_faces(tgt_body_meshes[0], to_delete)

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
        "fit": {**fit_stats, **cfg["fit"]},
        "mask": mask_stats,
        "motion": motion_stats,
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
