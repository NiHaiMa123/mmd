"""Deterministic cloth setup on an explicitly prepared, single-layer mesh.

The caller supplies garment partitioning and attachment weights; this helper
does not infer a character's body parts or modify its original geometry.
"""
from collections import defaultdict
import bpy


def configure(proxy,pin_group,colliders,*,first=1,last=450):
    if proxy.type!='MESH' or not proxy.data.polygons:raise ValueError('Cloth proxy must contain faces')
    if any(m.type=='CLOTH' for m in proxy.modifiers):raise ValueError('Cloth simulation already exists')
    group=proxy.vertex_groups.get(pin_group)
    if group is None:raise ValueError('Missing cloth pin group')
    if first>=last:raise ValueError('Invalid cloth frame interval')
    colliders=list(colliders)
    if not colliders or any(o.type!='MESH' for o in colliders):raise ValueError('Explicit mesh colliders required')
    # Every disconnected physical island needs a fully fixed anchor. A pin
    # group elsewhere on the same object is insufficient.
    adjacent=defaultdict(set)
    for e in proxy.data.edges:
        a,b=e.vertices;adjacent[a].add(b);adjacent[b].add(a)
    left={i for f in proxy.data.polygons for i in f.vertices};island_pins=[]
    while left:
        todo=[left.pop()];ids=[]
        while todo:
            i=todo.pop();ids.append(i)
            for j in adjacent[i]:
                if j in left:left.remove(j);todo.append(j)
        count=sum(any(g.group==group.index and g.weight>.999 for g in proxy.data.vertices[i].groups) for i in ids)
        if count<2:raise ValueError('Each cloth island needs at least two fully pinned vertices')
        island_pins.append({'vertices':len(ids),'fully_pinned':count})
    sim=proxy.modifiers.new('Actual mesh cloth simulation','CLOTH');s=sim.settings
    s.quality=8;s.mass=.22;s.air_damping=3.;s.tension_stiffness=32.;s.compression_stiffness=32.;s.shear_stiffness=18.;s.bending_stiffness=.7
    s.tension_damping=12.;s.compression_damping=12.;s.shear_damping=10.;s.bending_damping=3.;s.vertex_group_mass=group.name;s.pin_stiffness=1.;s.use_dynamic_mesh=False
    c=sim.collision_settings;c.use_collision=True;c.distance_min=.003;c.collision_quality=4;c.use_self_collision=True;c.self_distance_min=.002;c.self_friction=5.
    collection=bpy.data.collections.new(proxy.name+'_Colliders');bpy.context.scene.collection.children.link(collection)
    for collider in colliders:
        if not any(m.type=='COLLISION' for m in collider.modifiers):collider.modifiers.new('Cloth collision','COLLISION')
        collider.collision.thickness_outer=.002;collider.collision.thickness_inner=.001;collider.collision.damping_factor=.5
        collection.objects.link(collider)
    c.collection=collection;sim.point_cache.frame_start=first;sim.point_cache.frame_end=last
    proxy.hide_render=True
    return sim,{'solver':'Blender CLOTH mesh solver','island_pins':island_pins,'frames':[first,last],'self_collision':True,'portable_to_pmx':False}
