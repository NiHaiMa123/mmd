"""Simulate MMD physics inside Blender (P3-03 / P3-04 support).

mmd_tools does not map the MMD collision groups onto Blender's rigid body
collections, so a Bullet simulation of an imported model ignores the MMD
collision rules completely.  It also never drives the bones from the physics,
which is what MMD does for mode 1 / 2 rigid bodies.

This module fills both gaps:

  * the MMD collision group of every rigid body becomes a Blender collision
    collection, and the MMD collision mask becomes the collection
    membership, so two bodies collide exactly when MMD says they do;
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

    for r in rigids:
        g = _bone_group(r)
        if g not in coll_of:
            continue
        for c in list(r.users_collection):
            c.objects.unlink(r)
        coll_of[g].objects.link(r)
        rb = r.rigid_body
        mask = list(r.mmd_rigid.collision_group_mask)
        slots = [False] * 20
        for i, on in enumerate(mask):
            if on and i in slot_of:
                slots[slot_of[i]] = True
        rb.collision_collections = slots
        mode = _mode(r)
        # blender 5.x has no KINEMATIC type any more: a body stays ACTIVE and
        # the `kinematic` flag makes it follow its animation instead of the
        # simulation - that is MMD's mode 0 (follow bone)
        rb.type = 'ACTIVE'
        rb.kinematic = (mode == "0")
        rb.use_deactivation = False

    # the mode 0 colliders follow their bone
    follow = [(r, r.mmd_rigid.bone) for r in rigids
              if _mode(r) == "0" and r.mmd_rigid.bone in bones]
    for r, _b in follow:
        r.animation_data_clear()
    for f in range(first_frame, last_frame + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        for r, bone in follow:
            m = arm.matrix_world @ arm.pose.bones[bone].matrix
            r.location = m.to_translation()
            r.rotation_mode = 'QUATERNION'
            r.rotation_quaternion = m.to_quaternion()
            r.keyframe_insert("location", frame=f)
            r.keyframe_insert("rotation_quaternion", frame=f)

    # the physics drives the bones again (MMD mode 1 / 2)
    drive = [(r, r.mmd_rigid.bone) for r in rigids
             if _mode(r) in ("1", "2") and r.mmd_rigid.bone in bones]

    def apply_physics(scene=None, depsgraph=None):
        # blender calls the frame change handlers with (scene, depsgraph)
        dg = depsgraph or bpy.context.evaluated_depsgraph_get()
        inv = arm.matrix_world.inverted()
        for r, bone in drive:
            arm.pose.bones[bone].matrix = inv @ r.evaluated_get(dg).matrix_world
        bpy.context.view_layer.update()

    for h in list(bpy.app.handlers.frame_change_post):
        if getattr(h, "__name__", "") == HANDLER_NAME:
            bpy.app.handlers.frame_change_post.remove(h)
    apply_physics.__name__ = HANDLER_NAME
    bpy.app.handlers.frame_change_post.append(apply_physics)

    return {"rigid_bodies": len(rigids), "groups": groups,
            "slots": slot_of, "follow_bodies": len(follow),
            "driven_bones": len(drive),
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
