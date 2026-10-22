"""Simulate MMD physics inside Blender (P3-03 / P3-04 support).

mmd_tools does not map the MMD collision groups onto Blender's rigid body
collections, so a Bullet simulation of an imported model ignores the MMD
collision rules completely.  It also never drives the bones from the physics,
which is what MMD does for mode 1 / 2 rigid bodies.

This module fills both gaps:

  * the MMD collision group of every rigid body becomes a Blender collision
    collection, and the MMD collision mask becomes the collection
    membership, so two bodies collide when they share a layer - an
    approximation of the MMD rule, which needs both masks to allow the pair;
  * the MMD dynamics type becomes the Blender body type
    (0 follow bone -> KINEMATIC, 1 / 2 physics -> ACTIVE);
  * the mode 0 bodies are keyframed from the bone they follow, and a frame
    change handler copies the simulated motion of the mode 1 / 2 bodies back
    onto their bones - that is MMD's "physics drives the bone" step.

Usage (inside Blender, after importing a PMX and a VMD):

    from src import physics_sim
    physics_sim.setup(scene, arm_obj, first_frame, last_frame)
    physics_sim.run(scene, first_frame, last_frame)

The MMD collision mask is an "allowed to collide with" list - verified from
the models themselves: in 达妮娅 the hair sits in group 1 with the mask {1}
and the torso in group 0 with the mask {0}, so the two never collide.

MMD needs both directions to allow the pair: A's mask has to contain B's
group *and* B's mask has to contain A's group.  Blender's rigid body world
works with collection layers instead, and a body collides with another one
as soon as they share a layer - that is weaker than the MMD rule.  The
translation below is therefore an **approximation**: the physics QA says
whether the outfit is allowed to touch the base body, it is not a faithful
MMD simulation.  See docs/REVIEW.md (P0-02).
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

    MMD lets two bodies collide when A's mask contains B's group *and* B's
    mask contains A's group.  Blender only asks one side: a body touches
    every body in a collection it has enabled.  Measured on Blender 5.2.1
    (work/test_collision_filter.py): one side is enough.

    So the group list is narrowed down per body: a group is only kept when
    the bodies in it also allow this body's group.  With one mask per group
    that turns Blender's rule into MMD's rule exactly.
    """
    g = r.mmd_rigid.collision_group_number
    mask = list(r.mmd_rigid.collision_group_mask)
    if group_masks is None:
        group_masks = _group_masks([r])
    slots = [False] * 20
    for other, slot in slot_of.items():
        if other >= len(mask) or not mask[other]:
            continue
        other_mask = group_masks.get(other)
        if other_mask is None or g >= len(other_mask) or not other_mask[g]:
            continue
        slots[slot] = True
    return slots


def setup(scene: bpy.types.Scene, arm: bpy.types.Object,
          first_frame: int = 1, last_frame: int = 5000) -> dict[str, Any]:
    """Prepare the rigid body world so Bullet follows the MMD rules."""
    rigids = _rigids()
    if not rigids:
        return {"skipped": "no rigid bodies in the scene"}
    bones = set(arm.data.bones.keys())

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
    # how far the bodies drift from the bone they follow.  MMD keeps that
    # relation fixed, so a growing number means the simulation is pulling the
    # colliders away from the body.
    # The keys are written while the simulation is already running, so the
    # first pass writes the bodies one frame behind and the second pass
    # writes them where the simulation actually wants them.
    max_rel_error = 0.0
    for pass_index in range(2):
        for r, _b, _o in follow:
            r.animation_data_clear()
            r.rotation_mode = 'QUATERNION'
        if pass_index:
            # the point cache holds the result of the last pass; without
            # dropping it the simulation would not run again and the second
            # pass would just copy the first one
            cache = scene.rigidbody_world.point_cache
            cache.frame_start = first_frame - 1
            cache.frame_start = first_frame
        max_rel_error = 0.0
        for f in range(first_frame, last_frame + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            for r, bone, offset in follow:
                m = arm.matrix_world @ arm.pose.bones[bone].matrix
                if pass_index and f > first_frame:
                    got = m.inverted() @ r.matrix_world
                    err = max(abs(got[i][j] - offset[i][j])
                              for i in range(4) for j in range(4))
                    max_rel_error = max(max_rel_error, err)
                r.matrix_world = m @ offset
                r.keyframe_insert("location", frame=f)
                r.keyframe_insert("rotation_quaternion", frame=f)
                r.keyframe_insert("scale", frame=f)

    # the physics drives the bones again (MMD mode 1 / 2).  The bone keeps
    # the offset it had to its rigid body in the rest pose - MMD attaches the
    # body to the bone, it does not put the bone on the body.
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

    def apply_physics(scene=None, depsgraph=None):
        # blender calls the frame change handlers with (scene, depsgraph)
        dg = depsgraph or bpy.context.evaluated_depsgraph_get()
        inv = arm.matrix_world.inverted()
        for r, bone, offset in drive:
            world = r.evaluated_get(dg).matrix_world @ offset
            arm.pose.bones[bone].matrix = inv @ world
        bpy.context.view_layer.update()

    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == HANDLER_NAME:
            bpy.app.handlers.frame_change_post.remove(h)
    apply_physics.__name__ = HANDLER_NAME
    bpy.app.handlers.frame_change_post.append(apply_physics)

    # the groups do not always share a mask; the collision layers are built
    # per group, so a difference inside a group is worth reporting
    mixed = 0
    for r in rigids:
        g = r.mmd_rigid.collision_group_number
        if list(r.mmd_rigid.collision_group_mask) != group_masks.get(g):
            mixed += 1

    return {"rigid_bodies": len(rigids), "groups": groups,
            "slots": slot_of, "follow_bodies": len(follow),
            "driven_bones": len(drive),
            "mixed_group_masks": mixed,
            "max_follow_error": round(max_rel_error, 6),
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
