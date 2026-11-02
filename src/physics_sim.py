"""Blender physics diagnostics; these are not native MMD runtime acceptance.

Use setup_native: installed MMD Tools constructs parenting, rotation-only
mode-2 constraints and pairwise non-collision constraints. Diagnostics extend
the distance limit to cover all exclusions, then detach pre-physics kinematic
tracks. Feedback from secondary physics into those tracks is not simulated.

mmd_tools collision_group_mask True means EXCLUDED, whereas a raw PMX bit
True means ALLOWED. The former legacy layer/pose-handler solver remains as
setup_legacy_proxy for historical comparison and is not used by QA.
"""
from __future__ import annotations

from typing import Any

import bpy
from mathutils import Vector

HANDLER_NAME = "mmd_physics_to_bones"


def _rigids(objects=None) -> list[bpy.types.Object]:
    objects = objects if objects is not None else list(bpy.data.objects)
    return [o for o in objects
            if getattr(o, "mmd_type", "NONE") == "RIGID_BODY"]


def _bone_group(rb: bpy.types.Object) -> str:
    return rb.mmd_rigid.collision_group_number


def _mode(rb: bpy.types.Object) -> str:
    return str(rb.mmd_rigid.type)


def _group_masks(rigids: list[bpy.types.Object]) -> dict[int, list[bool]]:
    """The collision mask of every group.

    The bodies of one group normally share a mask; where they do not, the
    first one wins and the difference is reported by the caller.
    """
    out: dict[int, list[bool]] = {}
    for r in rigids:
        g = r.mmd_rigid.collision_group_number
        if g not in out:
            out[g] = list(r.mmd_rigid.collision_group_mask)
    return out


def collision_slots(r: bpy.types.Object, slot_of: dict[int, int],
                     group_masks: dict[int, list[bool]] | None = None
                     ) -> list[bool]:
    """Blender's collision layers for one body, with the MMD rule applied.

    Legacy layer approximation. mmd_tools True means excluded. Shared layer
    bits cannot encode arbitrary pairs, so prefer setup_native for simulation.
    """
    g = r.mmd_rigid.collision_group_number
    mask = list(r.mmd_rigid.collision_group_mask)
    if group_masks is None:
        group_masks = _group_masks([r])
    slots = [False] * 20
    for other, slot in slot_of.items():
        if other >= len(mask) or mask[other]:
            continue
        other_mask = group_masks.get(other)
        if other_mask is None or g >= len(other_mask) or other_mask[g]:
            continue
        slots[slot] = True
    return slots


def _bounding_radius(obj: bpy.types.Object) -> float:
    """A conservative radius of a rigid body's shape.

    The centre distance of two bodies says nothing about whether they can
    touch: a long skirt capsule and a thigh collider can be 30 cm apart and
    still meet.  The gap between the two bounding spheres is the measure
    that does.
    """
    me = getattr(obj, "data", None)
    if me is None or not hasattr(me, "vertices") or not len(me.vertices):
        return 0.0
    mw = obj.matrix_world
    c = mw.translation
    r = 0.0
    for v in me.vertices:
        d = (mw @ v.co - c).length
        if d > r:
            r = d
    return r


def _pair_table(rigids: list[bpy.types.Object]
                ) -> list[tuple[int, int, bool, bool]]:
    """(i, j, allowed by PMX mask, effective Blender filter) for each pair.

    The rules do not change while the simulation runs, so the table is
    built once and the per frame reports only have to measure distances.
    """
    blocked = {frozenset((o.rigid_body_constraint.object1, o.rigid_body_constraint.object2))
               for o in bpy.data.objects if o.rigid_body_constraint
               and o.rigid_body_constraint.enabled and o.rigid_body_constraint.disable_collisions}
    data = []
    for r in rigids:
        rb = r.rigid_body
        slots = list(rb.collision_collections) if rb else [False] * 20
        data.append((r.mmd_rigid.collision_group_number,
                     list(r.mmd_rigid.collision_group_mask),
                     set(i for i, on in enumerate(slots) if on)))
    table: list[tuple[int, int, bool, bool]] = []
    n = len(rigids)
    for i in range(n):
        gi, mi, li = data[i]
        for j in range(i + 1, n):
            gj, mj, lj = data[j]
            allowed = (gj < len(mi) and not mi[gj]) and (gi < len(mj) and not mj[gi])
            effective = bool(li & lj) and frozenset((rigids[i], rigids[j])) not in blocked
            table.append((i, j, allowed, effective))
    return table


def contact_matrix_report(rigids: list[bpy.types.Object],
                         positions: dict[str, Vector] | None = None,
                         near_dist: float = 0.12,
                         gap_dist: float = 0.02,
                         table: list[tuple[int, int, bool, bool]] | None = None
                         ) -> dict[str, Any]:
    """How far is Blender's collision rule from the MMD one?

    Compare mutual exclusions with shared Blender layers AND enabled
    no-collision constraints. MMD Tools adds those constraints only inside
    its configured distance, so far-away exclusions can still differ.
    Historical *_layer_pairs names are kept for report compatibility, but
    the effective filter now includes no-collision constraints.

    What is counted here are **potential pairs**, not contacts: nothing in
    this report says that bullet ever generated a contact manifold for a
    pair.  The "near" figures narrow the set down to the pairs that are
    close enough to ever touch, in two ways:

    * `near_*` compares the centre distance (12 cm by default);
    * `near_gap_*` compares the gap between the two bounding spheres, which
      is the conservative one - a long capsule and a thigh collider meet
      long before their centres do.

    `positions` has to be the positions of the bodies in the pose the report
    is about; a pose that was read after the simulation moved them describes
    the last frame, not the rest pose.
    """
    n = len(rigids)
    if n < 2:
        return {"pairs": 0}
    groups = [r.mmd_rigid.collision_group_number for r in rigids]
    radii = [_bounding_radius(r) for r in rigids]
    if table is None:
        table = _pair_table(rigids)
    false_positive = 0
    false_negative = 0
    expected_pairs = 0
    shared_pairs = 0
    near_fp = 0
    near_fn = 0
    near_pairs = 0
    gap_fp = 0
    gap_fn = 0
    gap_pairs = 0
    by_group: dict[tuple[int, int], list[int]] = {}
    near_by_group: dict[tuple[int, int], list[int]] = {}
    for i, j, allowed, shared in table:
        gi, gj = groups[i], groups[j]
        near = True
        gap = True
        if positions is not None:
            a = positions.get(rigids[i].name)
            b = positions.get(rigids[j].name)
            if a is None or b is None:
                near = False
                gap = False
            else:
                dist = (a - b).length
                near = dist <= near_dist
                gap = (dist - radii[i] - radii[j]) <= gap_dist
        if allowed:
            expected_pairs += 1
        if shared:
            shared_pairs += 1
        if allowed and not shared:
            false_negative += 1
            key = (min(gi, gj), max(gi, gj))
            by_group.setdefault(key, []).append(1)
            if near:
                near_by_group.setdefault(key, []).append(1)
                near_fn += 1
            if gap:
                gap_fn += 1
        elif shared and not allowed:
            false_positive += 1
            key = (min(gi, gj), max(gi, gj))
            by_group.setdefault(key, []).append(0)
            if near:
                near_by_group.setdefault(key, []).append(0)
                near_fp += 1
            if gap:
                gap_fp += 1
        if near:
            near_pairs += 1
        if gap:
            gap_pairs += 1
    worst = sorted(by_group.items(), key=lambda kv: len(kv[1]),
                   reverse=True)[:10]
    # the pairs Blender actually lets through are the ones that share a
    # layer; that number is expected - false negative + false positive, not
    # "all pairs"
    if shared_pairs != expected_pairs - false_negative + false_positive:
        raise AssertionError(
            f"the layer pair count does not add up: {shared_pairs} shared, "
            f"{expected_pairs} expected, {false_negative} missed, "
            f"{false_positive} wrong")
    return {
        "bodies": n,
        "pairs": n * (n - 1) // 2,
        "expected_pmx_filter_pairs": expected_pairs,
        "effective_blender_layer_pairs": shared_pairs,
        "false_positive_layer_pairs": false_positive,
        "false_negative_layer_pairs": false_negative,
        "near_center_distance": near_dist,
        "near_pairs": near_pairs,
        "near_false_positive": near_fp,
        "near_false_negative": near_fn,
        "near_gap_distance": gap_dist,
        "near_gap_pairs": gap_pairs,
        "near_gap_false_positive": gap_fp,
        "near_gap_false_negative": gap_fn,
        "worst_group_pairs": [
            {"groups": list(k), "differing": len(v),
             "near_differing": len(near_by_group.get(k, []))}
            for k, v in worst],
    }


def setup_native(scene, arm, first_frame=1, last_frame=5000, outfit_groups=None,
                 break_outfit_body=False):
    """Use the installed MMD Tools rig builder, including mode-2 rotation only.

    No frame handlers write pose matrices; no kinematic trajectories are baked
    from an already-running simulation. Results remain Blender Bullet results.
    """
    unregister()
    root = arm
    while root is not None and getattr(root, 'mmd_type', 'NONE') != 'ROOT':
        root = root.parent
    if root is not None and root.mmd_root.is_built:
        raise ValueError('Physics diagnostic requires a fresh unbuilt import; reimport the PMX')
    rigids = _rigids()
    if not rigids:
        raise ValueError('No MMD rigid bodies')
    if scene.rigidbody_world:
        scene.rigidbody_world.enabled = False
    tracks, bake_report = capture_kinematic_tracks(scene, arm, rigids, first_frame, last_frame)
    print('PHYSICS_CAPTURED: animation-only kinematic tracks', flush=True)
    broken = 0
    if break_outfit_body and outfit_groups:
        outfit = set(outfit_groups)
        body = {r.mmd_rigid.collision_group_number for r in rigids} - outfit
        for r in rigids:
            mask = list(r.mmd_rigid.collision_group_mask)
            for group in (body if r.mmd_rigid.collision_group_number in outfit else outfit):
                if not mask[group]:
                    mask[group] = True
                    broken += 1
            r.mmd_rigid.collision_group_mask = mask
    exclusion_scale = complete_exclusion_scale(rigids)
    scene.frame_set(first_frame)
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    arm.hide_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=exclusion_scale, collision_margin=1e-6)
    print('PHYSICS_BUILT: complete collision exclusions', flush=True)
    removed_relations = 0
    for rigid in rigids:
        bone_name = rigid.mmd_rigid.bone
        for constraint in list(rigid.constraints):
            if constraint.name == 'mmd_tools_rigid_parent' and constraint.mute:
                rigid.constraints.remove(constraint)
                removed_relations += 1
        rigid.mmd_rigid['bone'] = bone_name
    install_kinematic_tracks(tracks, first_frame)
    world = scene.rigidbody_world
    world.enabled = True
    world.substeps_per_frame = 10
    world.solver_iterations = 40
    world.point_cache.frame_start = first_frame
    world.point_cache.frame_end = last_frame
    bpy.context.view_layer.update()
    matrix = contact_matrix_report(rigids)
    if matrix['false_positive_layer_pairs'] or matrix['false_negative_layer_pairs']:
        raise RuntimeError('Exact PMX collision exclusion construction failed')
    print('PHYSICS_SETUP_READY: exact exclusions and detached pre-physics kinematic tracks', flush=True)
    modes = {str(i): sum(_mode(r) == str(i) for r in rigids) for i in range(3)}
    tracking = [c for p in arm.pose.bones for c in p.constraints if c.name == 'mmd_tools_rigid_track']
    return {'backend': 'mmd_tools.build_rig', 'rigid_bodies': len(rigids),
            'mode_counts': modes, 'mode2_bodies': modes['2'],
            'driven_bones': len(tracking), 'follow_bodies': modes['0'],
            'rotation_only_constraints': sum(c.type == 'COPY_ROTATION' for c in tracking),
            'transform_constraints': sum(c.type == 'COPY_TRANSFORMS' for c in tracking),
            'broken_mask_bits': broken, 'frames': [first_frame, last_frame],
            'contact_matrix': matrix, 'non_collision_distance_scale': exclusion_scale,
            'kinematic_bake': bake_report,
            'removed_muted_relations': removed_relations,
            'scope': 'MMD Tools Blender physics, not native MMD runtime equivalence'}


def complete_exclusion_scale(rigids):
    """Cover every excluded pair using the installed builder's own distance rule."""
    scale = 1.5
    sizes = [(Vector(r.bound_box[0])-Vector(r.bound_box[6])).length for r in rigids]
    for i, a in enumerate(rigids):
        for j in range(i+1, len(rigids)):
            b = rigids[j]
            if not (a.mmd_rigid.collision_group_mask[b.mmd_rigid.collision_group_number]
                    or b.mmd_rigid.collision_group_mask[a.mmd_rigid.collision_group_number]):
                continue
            span = (sizes[i]+sizes[j])*.5
            if span <= 1e-10:
                raise ValueError('Cannot build exact exclusions for two zero-size rigid bodies')
            scale = max(scale, (a.location-b.location).length/span + 1.)
    return scale


def capture_kinematic_tracks(scene, arm, rigids, first, last):
    """Capture animation before physics exists, never from a warmed simulation."""
    dynamic = {r.mmd_rigid.bone for r in rigids if _mode(r) != '0' and r.mmd_rigid.bone}
    def feedback(name):
        visited, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in visited:
                continue
            visited.add(n)
            if n in dynamic:
                return True
            bone = arm.pose.bones.get(n)
            if bone is None:
                continue
            if bone.parent:
                todo.append(bone.parent.name)
            todo.extend(c.subtarget for c in bone.constraints if getattr(c, 'target', None) == arm
                        and getattr(c, 'subtarget', '') and not c.mute)
        return False
    tracks = []
    for r in rigids:
        if _mode(r) != '0':
            continue
        name = r.mmd_rigid.bone
        rest = r.matrix_world.copy()
        offset = (arm.matrix_world @ arm.data.bones[name].matrix_local).inverted() @ rest if name in arm.data.bones else None
        tracks.append({'object': r, 'bone': name, 'offset': offset, 'rest': rest, 'values': []})
    for frame in range(first, last+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        evaluated = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        for track in tracks:
            matrix = (evaluated.matrix_world @ evaluated.pose.bones[track['bone']].matrix @ track['offset']
                      if track['offset'] is not None else track['rest'])
            track['values'].append((frame, matrix.copy()))
    scene.frame_set(first)
    return tracks, {'bodies': len(tracks), 'frames': [first, last],
                    'feedback_bones': sorted({t['bone'] for t in tracks if feedback(t['bone'])}),
                    'stage': 'animation only, captured before build_rig',
                    'limitation': 'secondary-physics feedback into kinematic followers is not simulated'}


def install_kinematic_tracks(tracks, first):
    for track in tracks:
        r = track['object']
        r.parent = None
        r.parent_type = 'OBJECT'
        # Muted constraints still create dependency-graph edges in Blender.
        # The imported diagnostic copy needs no live armature relation now.
        for constraint in list(r.constraints):
            r.constraints.remove(constraint)
        r.mmd_rigid['bone'] = track['bone']
        r.animation_data_clear()
        r.rotation_mode = 'QUATERNION'
        for frame, matrix in track['values']:
            r.location, r.rotation_quaternion, r.scale = matrix.decompose()
            for path in ('location', 'rotation_quaternion', 'scale'):
                r.keyframe_insert(path, frame=frame)
        r.matrix_world = track['values'][0][1]


def setup_legacy_proxy(scene: bpy.types.Scene, arm: bpy.types.Object,
          first_frame: int = 1, last_frame: int = 5000,
          outfit_groups: set[int] | None = None,
          break_outfit_body: bool = False) -> dict[str, Any]:
    """Prepare the rigid body world so Bullet follows the MMD rules.

    `break_outfit_body` switches the outfit off the base body's limbs before
    the collision layers are built.  It has to happen *here*: a counterfactual
    that is switched on after the simulation has already run is not the same
    model, it is the same model with a warmed up cache.
    """
    rigids = _rigids()
    if not rigids:
        return {"skipped": "no rigid bodies in the scene"}
    bones = set(arm.data.bones.keys())

    broken_bits = 0
    if break_outfit_body and outfit_groups:
        outfit = set(outfit_groups)
        body = {r.mmd_rigid.collision_group_number for r in rigids} - outfit
        for r in rigids:
            g = r.mmd_rigid.collision_group_number
            mask = list(r.mmd_rigid.collision_group_mask)
            # the outfit loses the body's groups, the body loses the outfit's
            other = body if g in outfit else outfit
            for og in other:
                if og < len(mask) and not mask[og]:
                    mask[og] = True
                    broken_bits += 1
            r.mmd_rigid.collision_group_mask = mask

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    # mmd_tools leaves the world switched off - without this the simulation
    # never advances and every body stands still
    world.enabled = True
    root = world.collection

    # every rigid body goes back under the world root first
    for r in rigids:
        if r.name not in root.objects:
            for c in list(r.users_collection):
                c.objects.unlink(r)
            root.objects.link(r)

    for c in list(bpy.data.collections):
        if c.name.startswith("mmd_grp_"):
            bpy.data.collections.remove(c)

    groups = sorted({_bone_group(r) for r in rigids})
    coll_of = {}
    for g in groups:
        c = bpy.data.collections.new(f"mmd_grp_{g}")
        root.children.link(c)
        # the collection also has to be part of the scene: a collection that
        # only hangs under the rigid body world is not in the view layer, and
        # then the bodies are never evaluated and bullet stays idle
        scene.collection.children.link(c)
        coll_of[g] = c
    children = list(root.children)
    slot_of = {g: children.index(c) for g, c in coll_of.items()}
    group_masks = _group_masks(rigids)

    mode_counts = {"0": 0, "1": 0, "2": 0}
    for r in rigids:
        mode_counts[_mode(r)] = mode_counts.get(_mode(r), 0) + 1

    for r in rigids:
        g = _bone_group(r)
        if g not in coll_of:
            continue
        for c in list(r.users_collection):
            c.objects.unlink(r)
        coll_of[g].objects.link(r)
        rb = r.rigid_body
        rb.collision_collections = collision_slots(r, slot_of, group_masks)
        mode = _mode(r)
        # blender 5.x has no KINEMATIC type any more: a body stays ACTIVE and
        # the `kinematic` flag makes it follow its animation instead of the
        # simulation - that is MMD's mode 0 (follow bone)
        rb.type = 'ACTIVE'
        rb.kinematic = (mode == "0")
        rb.use_deactivation = False

    # the mode 0 colliders follow their bone - and they keep the offset they
    # had in the rest pose.  MMD stores a rigid body relative to the bone it
    # follows, and putting it on the bone's origin instead moves every
    # collider of the body.
    bone_rest = {b: arm.matrix_world @ arm.data.bones[b].matrix_local
                 for b in bones}
    follow = []
    for r in rigids:
        bone = r.mmd_rigid.bone
        if _mode(r) != "0" or bone not in bones:
            continue
        offset = bone_rest[bone].inverted() @ r.matrix_world
        follow.append((r, bone, offset))
    for r, _b, _o in follow:
        r.animation_data_clear()
        r.rotation_mode = 'QUATERNION'

    # The physics drives the bones again (MMD mode 1 / 2).  The bone keeps
    # the offset it had to its rigid body in the rest pose - MMD attaches the
    # body to the bone, it does not put the bone on the body.
    # The offsets have to be taken *before* anything is simulated: once the
    # simulation has run, r.matrix_world is no longer the rest position.
    drive = []
    for r in rigids:
        bone = r.mmd_rigid.bone
        if _mode(r) not in ("1", "2") or bone not in bones:
            continue
        offset = (r.matrix_world.inverted() @ bone_rest[bone])
        drive.append((r, bone, offset))
    # the parents have to be written before their children: a pose matrix is
    # relative to the parent's pose, so writing a child first leaves it in
    # the space the parent had a frame ago - the whole chain would be off by
    # the parent's motion.
    def _depth(name: str) -> int:
        d = 0
        b = arm.data.bones.get(name)
        while b is not None and b.parent is not None:
            d += 1
            b = b.parent
        return d

    drive.sort(key=lambda item: _depth(item[1]))

    # A mode 0 body that follows a bone the physics drives cannot be worked
    # out from the animation alone - its trajectory depends on the
    # simulation, and the simulation depends on it.  Those bodies are
    # counted so the report can say how far the proxy can be trusted.
    driven_bones = {bone for _r, bone, _o in drive}
    feedback: list[str] = []
    for _r, bone, _o in follow:
        b = arm.data.bones.get(bone)
        while b is not None:
            if b.name in driven_bones:
                feedback.append(bone)
                break
            b = b.parent

    def apply_physics(scene=None, depsgraph=None):
        # blender calls the frame change handlers with (scene, depsgraph)
        dg = depsgraph or bpy.context.evaluated_depsgraph_get()
        inv = arm.matrix_world.inverted()
        for r, bone, offset in drive:
            world = r.evaluated_get(dg).matrix_world @ offset
            arm.pose.bones[bone].matrix = inv @ world
        bpy.context.view_layer.update()

    # The handler is installed before the bodies are baked: the colliders of
    # the mode 0 bodies have to follow the bones the physics drives, and that
    # only works when the physics -> bone step already runs.
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == HANDLER_NAME:
            bpy.app.handlers.frame_change_post.remove(h)
    apply_physics.__name__ = HANDLER_NAME
    bpy.app.handlers.frame_change_post.append(apply_physics)

    # how far the bodies drift from the bone they follow.  MMD keeps that
    # relation fixed, so a growing number means the simulation is pulling the
    # colliders away from the body.
    # The keys are written while the simulation is already running, so the
    # first pass writes the bodies one frame behind and the second pass
    # writes them where the simulation actually wants them.  The error is
    # therefore measured per frame and not only at the end - a single
    # number cannot tell a constant offset from a drift.
    errors: list[float] = []
    max_rel_error = 0.0
    worst_frame = first_frame
    for pass_index in range(2):
        for r, _b, _o in follow:
            r.animation_data_clear()
            r.rotation_mode = 'QUATERNION'
        if pass_index:
            # The point cache holds the result of the last pass; without
            # dropping it the simulation would not run again and the second
            # pass would just copy the first one.  Moving the start frame
            # and back invalidates the cache.
            # This is not a documented "free everything" call, so the
            # numbers it produces have to be read as a proxy and not as a
            # proof that the solver state was rebuilt.
            cache = scene.rigidbody_world.point_cache
            cache.frame_start = first_frame - 1
            cache.frame_start = first_frame
        max_rel_error = 0.0
        if pass_index:
            errors = []
        for f in range(first_frame, last_frame + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            for r, bone, offset in follow:
                m = arm.matrix_world @ arm.pose.bones[bone].matrix
                if pass_index and f > first_frame:
                    # the relation is measured on the translation: a matrix
                    # element difference says nothing about where the
                    # collider ended up
                    got = m.inverted() @ r.matrix_world
                    err = (got.translation - offset.translation).length
                    errors.append(err)
                    if err > max_rel_error:
                        max_rel_error = err
                        worst_frame = f
                r.matrix_world = m @ offset
                r.keyframe_insert("location", frame=f)
                r.keyframe_insert("rotation_quaternion", frame=f)
                r.keyframe_insert("scale", frame=f)

    # the groups do not always share a mask; the collision layers are built
    # per group, so a difference inside a group is worth reporting
    mixed = 0
    for r in rigids:
        g = r.mmd_rigid.collision_group_number
        if list(r.mmd_rigid.collision_group_mask) != group_masks.get(g):
            mixed += 1

    errors_sorted = sorted(errors)
    p95 = errors_sorted[int(len(errors_sorted) * 0.95)] if errors_sorted else 0.0
    mean = sum(errors) / len(errors) if errors else 0.0

    return {"rigid_bodies": len(rigids), "groups": groups,
            "slots": slot_of, "follow_bodies": len(follow),
            "driven_bones": len(drive),
            # mode 2 is a physics body whose rotation follows the bone;
            # blender cannot express that (a kinematic body is animated as
            # a whole), so those bodies are simulated as mode 1 and the
            # proxy is only as good as their number allows
            "mode_counts": mode_counts,
            "mode2_bodies": mode_counts.get("2", 0),
            # mode 0 bodies that follow a bone the physics drives: their
            # trajectory cannot be derived from the animation alone
            "feedback_bodies": len(feedback),
            "feedback_bone_names": sorted(set(feedback))[:20],
            "mixed_group_masks": mixed,
            "max_follow_error": round(max_rel_error, 6),
            "worst_follow_frame": worst_frame,
            "mean_follow_error": round(mean, 6),
            "p95_follow_error": round(p95, 6),
            "follow_error_samples": len(errors),
            "broken_mask_bits": broken_bits,
            "contact_matrix": contact_matrix_report(rigids),
            "frames": [first_frame, last_frame]}


def run(scene: bpy.types.Scene, first_frame: int, last_frame: int) -> dict[str, Any]:
    """Step the timeline so the simulation runs, frame by frame.

    Bullet only simulates when the frame advances one at a time from the point
    cache's start.  Jumping into the middle of the range leaves every body at
    its keyframed position - the simulation silently does nothing, and it looks
    exactly like "the physics is broken".

    The cache start is therefore pulled to the first frame we care about, and
    the range is stepped from there.
    """
    cache = scene.rigidbody_world.point_cache
    if cache.frame_start != first_frame:
        cache.frame_start = first_frame
    scene.frame_set(first_frame)
    scene.view_layers[0].update()
    for f in range(first_frame, last_frame + 1):
        scene.frame_set(f)
        scene.view_layers[0].update()
    return {"frames": [first_frame, last_frame],
            "cache_start": cache.frame_start}


def unregister() -> None:
    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == HANDLER_NAME:
            bpy.app.handlers.frame_change_post.remove(h)
