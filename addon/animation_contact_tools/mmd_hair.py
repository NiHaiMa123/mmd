"""MMD Tools/Bullet adapter: hair dynamics against animated body colliders.

This is a backend experiment, not a complete surface collision certificate.
Other rigs can use Bone Physics/Wiggle adapters with the same surface audit.
"""
from collections import Counter
import bpy
from mathutils import Quaternion
from .physics_world import ensure_world_members

def build_hair_only(mesh,arm,profile,padding=.004):
    if abs(float(profile.get('units_to_m',1.))-1.)>1e-9:raise ValueError('MMD Bullet experiment currently requires metre world coordinates')
    mode=profile.get('hair_mmd_rigid_mode','preserve')
    if mode not in ('preserve','hybrid','legacy_physics'):raise ValueError('Unknown hair_mmd_rigid_mode')
    if not hasattr(bpy.types.Object,'mmd_rigid'):raise RuntimeError('Enable MMD Tools before using its hair backend')
    root=arm
    while root and getattr(root,'mmd_type','')!='ROOT':root=root.parent
    if root is None:raise ValueError('This backend requires an MMD model root; choose a generic bone-physics backend for other rigs')
    if root.mmd_root.is_built:raise ValueError('Start from an unbuilt reference rig; do not rebuild an existing simulation silently')
    attr=mesh.data.attributes[profile['surface_attribute']];hair_ids={i for f in mesh.data.polygons if attr.data[f.index].value in profile['hair_classes'] for i in f.vertices}
    body_ids={i for f in mesh.data.polygons if attr.data[f.index].value in profile['body_classes']+profile['head_classes'] for i in f.vertices}
    names={g.index:g.name for g in mesh.vertex_groups};hair_bones={names[g.group] for i in hair_ids for g in mesh.data.vertices[i].groups if g.weight>.01 and names[g.group] in arm.data.bones}
    body_bones={names[g.group] for i in body_ids for g in mesh.data.vertices[i].groups if g.weight>.01 and names[g.group] in arm.data.bones}
    dynamic=set()
    for name in hair_bones:
        b=arm.data.bones[name]
        while b and b.name not in profile.get('root_hair_anchor_bones',[]):dynamic.add(b.name);b=b.parent
    initial=profile.get('hair_initial_pose',{})
    if set(initial)-dynamic:raise ValueError('Initial hair pose must only reference movable hair bones')
    for name,values in initial.items():
        if len(values)!=4:raise ValueError('Hair initial rotations must be quaternions')
        q=Quaternion(values);q.normalize();arm.pose.bones[name].rotation_quaternion=q
    if initial:arm.update_tag();bpy.context.view_layer.update()
    kinematic=set(profile.get('hair_kinematic_bones',[]))
    if profile.get('hair_pin_chain_roots',False):kinematic.update(n for n in dynamic if arm.data.bones[n].parent and arm.data.bones[n].parent.name in profile.get('root_hair_anchor_bones',[]))
    rigids=[o for o in root.children_recursive if getattr(o,'mmd_type','')=='RIGID_BODY'];keep=[];remove=[];moving=[];static=[];hair_static=[];original_types=Counter()
    for o in rigids:
        bone=o.mmd_rigid.bone
        if bone in dynamic:
            original_types[str(o.mmd_rigid.type)]+=1
            if bone in kinematic:o.mmd_rigid.type='0'
            if str(o.mmd_rigid.type)!='0':
                if mode=='hybrid':o.mmd_rigid.type='2'
                elif mode=='legacy_physics':o.mmd_rigid.type='1'
                moving.append(o)
            else:hair_static.append(o)
            o.mmd_rigid.collision_group_number=1;o.mmd_rigid.collision_group_mask=tuple(i==1 for i in range(16));keep.append(o)
        elif bone in body_bones or bone in profile.get('root_hair_anchor_bones',[]):
            o.mmd_rigid.type='0';o.mmd_rigid.collision_group_number=0;o.mmd_rigid.collision_group_mask=tuple(i==0 for i in range(16))
            size=list(o.mmd_rigid.size)
            if o.mmd_rigid.shape=='SPHERE':size[0]+=padding
            elif o.mmd_rigid.shape=='CAPSULE':size[0]+=padding
            else:size=[v+padding for v in size]
            o.mmd_rigid.size=size;static.append(o);keep.append(o)
        else:remove.append(o)
    keep_set=set(keep);moving_set=set(moving);removed_joints=0
    for o in list(root.children_recursive):
        if getattr(o,'mmd_type','')!='JOINT':continue
        c=o.rigid_body_constraint
        if not c or c.object1 not in keep_set or c.object2 not in keep_set or not ({c.object1,c.object2}&moving_set):
            bpy.data.objects.remove(o,do_unlink=True);removed_joints+=1
    for o in remove:bpy.data.objects.remove(o,do_unlink=True)
    for o in bpy.context.selected_objects:o.select_set(False)
    root.hide_viewport=False;root.hide_set(False);root.select_set(True);bpy.context.view_layer.objects.active=root;bpy.context.view_layer.update()
    # MMD Tools creates pair exclusions only inside this distance multiplier.
    # Zero suppresses almost every non-jointed exclusion; it does NOT mean
    # unrestricted filtering. Use an explicit complete filter for this model.
    non_collision_scale=float(profile.get('hair_non_collision_distance_scale',1e6))
    bpy.ops.mmd_tools.build_rig(non_collision_distance_scale=non_collision_scale,collision_margin=.001)
    attached_pairs=0
    if profile.get('hair_ignore_connected_anchor_collision',True):
        for obj in root.children_recursive:
            constraint=obj.rigid_body_constraint
            if getattr(obj,'mmd_type','')=='JOINT' and constraint and ({constraint.object1,constraint.object2}&moving_set):
                if not constraint.disable_collisions:attached_pairs+=1
                constraint.disable_collisions=True
    ignored=set();all_hair_set=moving_set|set(hair_static)
    for obj in root.children_recursive:
        constraint=obj.rigid_body_constraint
        if constraint and constraint.disable_collisions and constraint.object1 in all_hair_set and constraint.object2 in all_hair_set and ({constraint.object1,constraint.object2}&moving_set):ignored.add(frozenset((constraint.object1,constraint.object2)))
    expected=len(moving)*(len(moving)-1)//2+len(moving)*len(hair_static)
    world=bpy.context.scene.rigidbody_world
    # Imported/assembled scenes can retain Rigidbody properties while losing
    # world.collection. build_rig updates constraints, but does not relink these
    # existing objects. With no members, "simulation" is only driven bone pose.
    constraints=[o for o in root.children_recursive if o.rigid_body_constraint]
    membership=ensure_world_members(keep,constraints)
    world.enabled=True;world.substeps_per_frame=20;world.solver_iterations=40;world.point_cache.frame_start=1;world.point_cache.frame_end=450
    return {'backend':'MMD Tools / Blender Bullet','dynamic_hair_rigids':len(moving),'animated_body_rigids':len(static),
      'removed_irrelevant_rigids':len(remove),'removed_irrelevant_joints':removed_joints,'body_collider_padding_m':padding,
      **membership,
      'hair_self_collision':len(ignored)!=expected,'verified_disabled_hair_pairs':len(ignored),'expected_disabled_hair_pairs':expected,'non_collision_distance_scale':non_collision_scale,'connected_anchor_pairs_ignored':attached_pairs,'dynamic_bones':sorted(dynamic),'kinematic_hair_bones':sorted(kinematic),'hair_rigid_mode':mode,'original_hair_rigid_types':dict(original_types),'final_dynamic_types':dict(Counter(str(o.mmd_rigid.type) for o in moving)),'preserved_static_hair_rigids':len(hair_static),'physics_scope':'hair vs animated body only; proxy collision requires actual mesh verification'}
