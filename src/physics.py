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


def _collision_translation(src_objects: list[bpy.types.Object],
                           tgt_objects: list[bpy.types.Object],
                           garment_bones: set[str]):
    """Work out how the outfit's collision groups map onto the target's.

    The two models do not number their collision groups the same way:
    刻晴 keeps the legs in group 1 and the arms in group 2, 达妮娅 keeps both
    in group 0 and the feet in group 7.  A skirt that is copied verbatim looks
    for group 1, finds nothing, and swings straight through the legs.

    So the *relationship* is translated instead of the raw numbers: every
    source body group is mapped onto the target groups of the same bones, and
    the outfit's own groups are moved into groups the target does not use.
    """
    src_body: dict[str, tuple[int, list[bool]]] = {}
    for o in src_objects:
        if getattr(o, "mmd_type", "NONE") != "RIGID_BODY":
            continue
        bone = o.mmd_rigid.bone
        if not bone or bone in garment_bones:
            continue
        src_body.setdefault(bone, (o.mmd_rigid.collision_group_number,
                                   list(o.mmd_rigid.collision_group_mask)))

    tgt_body: dict[str, tuple[int, list[bool], bpy.types.Object]] = {}
    tgt_bone_groups: dict[str, set[int]] = {}
    for o in tgt_objects:
        if getattr(o, "mmd_type", "NONE") != "RIGID_BODY":
            continue
        bone = o.mmd_rigid.bone
        if not bone or bone in garment_bones:
            continue
        tgt_bone_groups.setdefault(bone, set()).add(
            o.mmd_rigid.collision_group_number)
        if bone not in tgt_body:
            tgt_body[bone] = (o.mmd_rigid.collision_group_number,
                              list(o.mmd_rigid.collision_group_mask), o)

    # source body group -> the target groups of the same bones
    src_group_bones: dict[int, set[str]] = {}
    for bone, (sg, _sm) in src_body.items():
        src_group_bones.setdefault(sg, set()).add(bone)
    group_map: dict[int, set[int]] = {}
    for sg, bones in src_group_bones.items():
        groups: set[int] = set()
        for b in bones:
            groups |= tgt_bone_groups.get(b, set())
        if groups:
            group_map[sg] = groups

    return src_body, tgt_body, group_map


def _fresh_groups(tgt_objects: list[bpy.types.Object],
                  wanted: list[int]) -> dict[int, int]:
    """Move the outfit's collision groups into groups the target does not use."""
    used = set()
    for o in tgt_objects:
        if getattr(o, "mmd_type", "NONE") == "RIGID_BODY":
            used.add(o.mmd_rigid.collision_group_number)
    out: dict[int, int] = {}
    for g in wanted:
        if g in out:
            continue
        n = g
        while n in used:
            n += 1
        used.add(n)
        out[g] = n
    return out


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

    src_body_rb, tgt_body_rb, group_map = _collision_translation(
        src_objects, tgt_objects, garment_bones)
    # the outfit's own groups are moved out of the way of the target's
    outfit_groups = sorted({o.mmd_rigid.collision_group_number for o in selected})
    fresh = _fresh_groups(tgt_objects, outfit_groups)

    created: dict[str, bpy.types.Object] = {}
    skipped: list[str] = []
    for o in selected:
        bone = o.mmd_rigid.bone
        d = deltas.get(bone)
        if d is None:
            skipped.append(o.name)
            continue
        # the mask is translated: a bit that pointed at a source body group
        # now points at the target groups of the same bones
        src_mask = list(o.mmd_rigid.collision_group_mask)
        new_mask = [False] * len(src_mask)
        for s, on in enumerate(src_mask):
            if not on:
                continue
            if s in fresh:
                new_mask[fresh[s]] = True
            for t_g in group_map.get(s, ()):
                if t_g < len(new_mask):
                    new_mask[t_g] = True
        new_group = fresh.get(o.mmd_rigid.collision_group_number,
                              o.mmd_rigid.collision_group_number)
        # A PMX rigid body is stored as an offset from the bone it follows, so
        # the rest delta has to be applied to the *bone*, not to the world
        # position.  Using the world position put every migrated rigid body
        # metres away from the model - the skirt's colliders ended up three
        # metres behind the character, which is why the physics never did
        # anything.
        # mmd_tools writes the rigid body's *world* transform into the PMX
        # (exporter.py: p_rigid.location = obj.matrix_world.translation) and
        # reads it back the same way (importer.py: loc = Vector(loc_data)...),
        # so the world position is what has to be written.
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
            collision_group_number=new_group,
            collision_group_mask=new_mask,
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

    # The base model's big limb colliders (the ones whose mask allows every
    # group) are what the outfit has to hit.  刻晴's own skirt is configured
    # with a mask of {6} - it never collided with the legs in the source
    # model either - so copying the relationship is not enough, the
    # relationship has to be added.
    limb_groups: set[int] = set()
    for _bone, (_g, _m, _o) in tgt_body_rb.items():
        if all(_m):
            limb_groups.add(_g)

    # the target's body rigid bodies have to allow the outfit's groups the
    # same way the source's body rigid bodies allowed them
    body_mask_fixes = 0
    for bone, (_tg, _tm, obj) in tgt_body_rb.items():
        twin = src_body_rb.get(bone)
        if twin is None:
            continue
        src_mask = twin[1]
        mask = list(obj.mmd_rigid.collision_group_mask)
        changed = False
        for g in outfit_groups:
            if g < len(src_mask) and src_mask[g]:
                n = fresh[g]
                if n < len(mask) and not mask[n]:
                    mask[n] = True
                    changed = True
        if changed:
            obj.mmd_rigid.collision_group_mask = mask
            body_mask_fixes += 1

    # open the outfit up against the base body's limbs
    opened = 0
    for o in created.values():
        rb = o.mmd_rigid
        mask = list(rb.collision_group_mask)
        changed = False
        for g in limb_groups:
            if g < len(mask) and not mask[g]:
                mask[g] = True
                changed = True
        if changed:
            rb.collision_group_mask = mask
            opened += 1

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
        "body_mask_fixes": body_mask_fixes,
        "limb_groups": sorted(limb_groups),
        "opened_to_limbs": opened,
        "group_map": {str(k): sorted(v) for k, v in group_map.items()},
        "outfit_groups": {str(k): v for k, v in fresh.items()},
        "rigid_bodies_skipped": len(skipped),
        "joints": joints_created,
        "joints_skipped": joints_skipped,
        "bones": sorted(garment_bones & set(deltas.keys()))[:10],
    }
