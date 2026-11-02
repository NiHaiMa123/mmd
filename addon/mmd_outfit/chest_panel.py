"""Recover a tailored panel from original UV-corresponding coordinates.

The target skin is an obstacle, not the panel's design surface. The original
panel retains its topology/UV; a smooth clearance field expands it as needed.
"""
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


def restore(cloth,body,arm,faces,template,*,margin=.003,transfer_weights=True):
    if not faces or any(not 0<=i<len(cloth.data.polygons) for i in faces):raise ValueError('Explicit valid garment faces required')
    ids=sorted({i for fi in faces for i in cloth.data.polygons[fi].vertices});index={i:k for k,i in enumerate(ids)};affine=np.array(template['affine']);source=np.array([template['vertices'][str(i)] for i in ids]);original=np.array([cloth.data.vertices[i].co[:] for i in ids]);positions=np.column_stack([source,np.ones(len(source))])@affine
    if template.get('blend_boundaries'):
        low,high=template.get('boundary_blend_ranges',((1.08,1.145),(1.33,1.373)));z=original[:,2];bottom=np.clip((z-low[0])/(low[1]-low[0]),0.,1.);top=np.clip((high[1]-z)/(high[1]-high[0]),0.,1.);blend=np.minimum(bottom,top);blend=blend*blend*(3-2*blend);positions=positions*blend[:,None]+original*(1-blend[:,None])
    normals=np.array([template['normals'][str(i)] for i in ids]);front=positions[:,1]<template.get('front_y_limit',-.015)
    skin_roles=set(template.get('skin_materials',('Body',)));ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());skin=ev.to_mesh();skin.calc_loop_triangles();transform=cloth.matrix_world.inverted()@body.matrix_world;points=[transform@v.co for v in skin.vertices];triangles=[t for t in skin.loop_triangles if skin.materials[t.material_index].mmd_material.name_j in skin_roles and any(1.07<points[i].z<1.40 and abs(points[i].x)<.19 for i in t.vertices)];tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True)
    # Mesh-space obstacle solve spreads local clearance across the smooth
    # original panel instead of pushing isolated vertices into small bumps.
    floor=np.zeros(len(ids));body_hits={}
    for k,p in enumerate(positions):
        if not front[k]:continue
        hit,normal,ti,distance=tree.ray_cast(Vector((p[0],-.5,p[2])),Vector((0,1,0)),1.)
        if hit is not None:floor[k]=max(0.,p[1]-hit.y+margin);body_hits[k]=(hit,ti)
    neighbors=[set() for i in ids]
    for e in cloth.data.edges:
        a,b=e.vertices
        if a in index and b in index:neighbors[index[a]].add(index[b]);neighbors[index[b]].add(index[a])
    shift=floor.copy()
    for _ in range(120):
        average=np.array([np.mean(shift[list(n)]) if n else shift[k] for k,n in enumerate(neighbors)]);shift=np.maximum(floor,average*.97);shift[~front]=0.
    positions[:,1]-=shift
    delta=positions-original
    keys=cloth.data.shape_keys.key_blocks if cloth.data.shape_keys else []
    for key in keys:
        for k,i in enumerate(ids):key.data[i].co+=Vector(delta[k])
    for k,i in enumerate(ids):cloth.data.vertices[i].co=positions[k]
    selection=cloth.data.attributes.get('OutfitStructuredClothSelection');removed=0
    if selection:
        for i in ids:removed+=selection.data[i].value;selection.data[i].value=False
    weights_changed=0;valid=set(arm.data.bones.keys());body_names={g.index:g.name for g in body.vertex_groups}
    if transfer_weights:
        for k,i in enumerate(ids):
            if k in body_hits:hit,ti=body_hits[k]
            else:
                hit,_,ti,distance=tree.find_nearest(Vector(positions[k]))
                if hit is None or distance>.055:continue
            tri=triangles[ti];w=barycentric_transform(hit,*(points[j] for j in tri.vertices),Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)));weights={}
            for j,bw in zip(tri.vertices,w):
                for g in body.data.vertices[j].groups:
                    name=body_names[g.group]
                    if name=='頭':name='首'
                    # A chest plate bridges the breasts rather than wrapping
                    # the nearest upper arm. Keep arm/shoulder motion out of
                    # its lower area; the collar transition can follow them.
                    if template.get('torso_weight_guard') and original[k,2]<template.get('torso_guard_below_z',1.30) and any(part in name for part in ('腕','肩','ひじ','手')):
                        name='上半身3' if '上半身3' in valid else '上半身2'
                    if name in valid:weights[name]=weights.get(name,0.)+max(0.,bw)*g.weight
            top=sorted(weights.items(),key=lambda x:-x[1])[:4];total=sum(v for _,v in top)
            if total<=0:continue
            for g in list(cloth.data.vertices[i].groups):
                if cloth.vertex_groups[g.group].name in valid:cloth.vertex_groups[g.group].remove([i])
            for name,value in top:
                group=cloth.vertex_groups.get(name) or cloth.vertex_groups.new(name=name);group.add([i],value/total,'REPLACE')
            weights_changed+=1
    ev.to_mesh_clear();cloth.data.update()
    if template.get('restore_shading_normals'):
        # Authored PMX normals are design data too. Recover them through the
        # same UV correspondence instead of smoothing the entire outfit.
        transformed=normals@np.linalg.inv(affine[:3,:3]).T;transformed/=np.maximum(np.linalg.norm(transformed,axis=1)[:,None],1e-12)
        loop_normals=[tuple(cloth.data.corner_normals[li].vector) for li in range(len(cloth.data.loops))]
        for f in cloth.data.polygons:
            for li in f.loop_indices:
                i=cloth.data.loops[li].vertex_index
                if i in index:
                    k=index[i];normal=Vector(transformed[k])
                    if template.get('blend_boundaries'):normal=(normal*blend[k]+Vector(loop_normals[li])*(1-blend[k])).normalized()
                    loop_normals[li]=tuple(normal)
        cloth.data.normals_split_custom_set(loop_normals)
    cloth.update_tag(refresh={'DATA'})
    return {'method':'original panel reconstruction with smooth target-skin obstacle clearance','vertices':len(ids),'faces':len(faces),'margin_m':margin,'max_displacement_m':float(np.linalg.norm(delta,axis=1).max()),'max_obstacle_expansion_m':float(shift.max()),'obstacle_ray_hits':len(body_hits),'weights_transferred':weights_changed,'removed_from_cloth_simulation':removed,'topology_uv_unchanged':True,'all_morph_deltas_preserved':True}
