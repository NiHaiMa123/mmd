"""Verify actual Bullet world membership, not only object property presence."""
import bpy


def ensure_world_members(rigids, constraints=()):
    scene=bpy.context.scene
    if scene.rigidbody_world is None:bpy.ops.rigidbody.world_add()
    world=scene.rigidbody_world
    if world.collection is None:
        collection=bpy.data.collections.new('HairContact_RigidBodyWorld')
        scene.collection.children.link(collection);world.collection=collection
    members=set(world.collection.all_objects);missing=[o for o in rigids if o not in members]
    for obj in missing:
        if obj.rigid_body is None:raise ValueError('World member has no RigidBody: '+obj.name)
        world.collection.objects.link(obj)
    if world.constraints is None:
        collection=bpy.data.collections.new('HairContact_ConstraintWorld')
        scene.collection.children.link(collection);world.constraints=collection
    members=set(world.constraints.all_objects);missing_constraints=[o for o in constraints if o not in members]
    for obj in missing_constraints:
        if obj.rigid_body_constraint is None:raise ValueError('Missing rigid constraint: '+obj.name)
        world.constraints.objects.link(obj)
    assert set(rigids)<=set(world.collection.all_objects)
    assert set(constraints)<=set(world.constraints.all_objects)
    return {'world_rigid_members':len(world.collection.all_objects),'world_rigids_relinked':len(missing),
            'world_constraint_members':len(world.constraints.all_objects),'world_constraints_relinked':len(missing_constraints)}
