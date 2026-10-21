"""Physics migration (P3-02): carry the outfit physics to the target model.

An MMD outfit's physics is a set of rigid bodies and joints.  Each rigid body
follows a bone, each joint connects two rigid bodies.  Migrating them means:

  * create the same rigid bodies in the target, at the transformed position
  * create the same joints, re-pointed at the migrated rigid bodies
  * re-point the joints that connect to the *body's* rigid bodies at the
    target's own rigid body for the same bone

The position of a rigid body follows the bone it is attached to, so the rest
delta of that bone gives the new position.  The size is scaled by how much
that bone grew, because the two bodies are not the same size.
"""
from __future__ import annotations

import importlib
from typing import Any

import bpy
from mathutils import Euler, Matrix, Vector


def _mmd_rigid_core():
    """The mmd_tools rigid body helpers.

    The addon lives in an extension namespace on Blender 4.2+ and under the
    plain name on older installs, so both are tried.
    """
    last: Exception | None = None
    for name in ("bl_ext.blender_org.mmd_tools.core.rigid_body",
                 "mmd_tools.core.rigid_body"):
        try:
            return importlib.import_module(name)
        except Exception as exc:                    # noqa: BLE001
            last = exc
    raise ImportError(f"mmd_tools rigid body helpers not found: {last}")


def _groups(target_objects: list[bpy.types.Object]):
    """The target's rigid body group and joint group empties."""
    rigid_group = None
    joint_group = None
    for o in target_objects:
        t = getattr(o, "mmd_type", "NONE")
        if t == "RIGID_GRP_OBJ" and rigid_group is None:
            rigid_group = o
        elif t == "JOINT_GRP_OBJ" and joint_group is None:
            joint_group = o
    return rigid_group, joint_group


def _bone_length(armature: bpy.types.Object, name: str) -> float | None:
    b = armature.data.bones.get(name)
    if b is None:
        return None
    return (b.tail_local - b.head_local).length


def migrate_physics(src_objects: list[bpy.types.Object],
                    tgt_objects: list[bpy.types.Object],
                    src_arm: bpy.types.Object, tgt_arm: bpy.types.Object,
                    deltas: dict[str, Matrix],
                    garment_bones: set[str]) -> dict[str, Any]:
    """Copy the outfit's rigid bodies and joints into the target model."""
    core = _mmd_rigid_core()
    FnRigidBody = core.FnRigidBody

    src_rigids = [o for o in src_objects
                  if getattr(o, "mmd_type", "NONE") == "RIGID_BODY"]
    src_joints = [o for o in src_objects
                  if getattr(o, "mmd_type", "NONE") == "JOINT"]
    if not src_rigids:
        return {"skipped": "the source has no rigid bodies"}

    rigid_group, joint_group = _groups(tgt_objects)
    if rigid_group is None or joint_group is None:
        return {"skipped": "the target model has no rigid / joint group"}

    # the target's own rigid bodies, indexed by the bone they follow
    tgt_by_bone: dict[str, bpy.types.Object] = {}
    for o in tgt_objects:
        if getattr(o, "mmd_type", "NONE") != "RIGID_BODY":
            continue
        bone = o.mmd_rigid.bone
        if bone and bone not in tgt_by_bone:
            tgt_by_bone[bone] = o

    # the outfit's rigid bodies: the ones riding on the outfit's own bones
    selected = [o for o in src_rigids
                if o.mmd_rigid.bone in garment_bones]
    if not selected:
        return {"skipped": "no rigid body rides on an outfit bone"}

    created: dict[str, bpy.types.Object] = {}
    skipped: list[str] = []
    for o in selected:
        bone = o.mmd_rigid.bone
        d = deltas.get(bone)
        if d is None:
            skipped.append(o.name)
            continue
        loc = d @ o.matrix_world.translation
        rot_src = o.matrix_world.to_euler("YXZ")
        rot = (d.to_3x3() @ rot_src.to_matrix()).to_euler("YXZ")

        # the size follows how much the bone changed
        src_len = _bone_length(src_arm, bone)
        tgt_len = _bone_length(tgt_arm, bone)
        scale = 1.0
        if src_len and tgt_len and src_len > 1e-6:
            scale = tgt_len / src_len
        size = Vector(o.mmd_rigid.size) * scale

        new = FnRigidBody.new_rigid_body_object(bpy.context, rigid_group)
        rb = o.rigid_body
        FnRigidBody.setup_rigid_body_object(
            new,
            shape_type=core.shapeType(o.mmd_rigid.shape),
            location=loc,
            rotation=rot,
            size=size,
            dynamics_type=int(o.mmd_rigid.type),
            collision_group_number=o.mmd_rigid.collision_group_number,
            collision_group_mask=list(o.mmd_rigid.collision_group_mask),
            name=o.name,
            name_e=o.mmd_rigid.name_e,
            bone=bone,
            friction=rb.friction if rb else 0.5,
            mass=rb.mass if rb else 1.0,
            angular_damping=rb.angular_damping if rb else 0.5,
            linear_damping=rb.linear_damping if rb else 0.05,
            bounce=rb.restitution if rb else 0.0,
        )
        if rb is not None:
            new.rigid_body.kinematic = rb.kinematic
            new.rigid_body.collision_shape = rb.collision_shape
            new.rigid_body.use_margin = rb.use_margin
            new.rigid_body.collision_margin = rb.collision_margin
        created[o.name] = new

    # the joints: re-point the endpoints
    def endpoint(name: str):
        """The target object for a source rigid body name."""
        if name in created:
            return created[name]
        src = next((r for r in src_rigids if r.name == name), None)
        if src is None:
            return None
        bone = src.mmd_rigid.bone
        return tgt_by_bone.get(bone)

    joints_created = 0
    joints_skipped = 0
    for j in src_joints:
        rbc = j.rigid_body_constraint
        if rbc is None or rbc.object1 is None or rbc.object2 is None:
            continue
        o1 = endpoint(rbc.object1.name)
        o2 = endpoint(rbc.object2.name)
        if o1 is None or o2 is None:
            joints_skipped += 1
            continue
        # only the joints that belong to the outfit
        if rbc.object1.name not in created and rbc.object2.name not in created:
            joints_skipped += 1
            continue

        loc = j.matrix_world.translation
        rot = j.matrix_world.to_euler("YXZ")
        bone = next((created[n].mmd_rigid.bone for n in
                     (rbc.object1.name, rbc.object2.name)
                     if n in created), None)
        d = deltas.get(bone)
        if d is not None:
            loc = d @ loc
            rot = (d.to_3x3() @ rot.to_matrix()).to_euler("YXZ")

        new = FnRigidBody.new_joint_object(bpy.context, joint_group, 1.0)
        nrbc = new.rigid_body_constraint
        nrbc.object1 = o1
        nrbc.object2 = o2
        for attr in ("limit_lin_x_lower", "limit_lin_x_upper",
                     "limit_lin_y_lower", "limit_lin_y_upper",
                     "limit_lin_z_lower", "limit_lin_z_upper",
                     "limit_ang_x_lower", "limit_ang_x_upper",
                     "limit_ang_y_lower", "limit_ang_y_upper",
                     "limit_ang_z_lower", "limit_ang_z_upper"):
            try:
                setattr(nrbc, attr, getattr(rbc, attr))
            except Exception:
                pass
        try:
            nrbc.use_spring_x = rbc.use_spring_x
            nrbc.use_spring_y = rbc.use_spring_y
            nrbc.use_spring_z = rbc.use_spring_z
            nrbc.spring_stiffness_x = rbc.spring_stiffness_x
            nrbc.spring_stiffness_y = rbc.spring_stiffness_y
            nrbc.spring_stiffness_z = rbc.spring_stiffness_z
            nrbc.spring_damping_x = rbc.spring_damping_x
            nrbc.spring_damping_y = rbc.spring_damping_y
            nrbc.spring_damping_z = rbc.spring_damping_z
        except Exception:
            pass
        new.mmd_joint.name_j = j.mmd_joint.name_j
        new.mmd_joint.name_e = j.mmd_joint.name_e
        new.mmd_joint.spring_linear = j.mmd_joint.spring_linear
        new.mmd_joint.spring_angular = j.mmd_joint.spring_angular
        new.location = loc
        new.rotation_euler = rot
        joints_created += 1

    return {
        "rigid_bodies": len(created),
        "rigid_bodies_skipped": len(skipped),
        "joints": joints_created,
        "joints_skipped": joints_skipped,
        "bones": sorted(garment_bones & set(deltas.keys()))[:10],
    }
