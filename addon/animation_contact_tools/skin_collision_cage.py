"""Watertight voxel skin cage, bound from a chosen evaluated pose to source LBS.

The cage is an approximation. Visible-surface contact must still be audited.
"""
from collections import Counter
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .surface import coords


def build_skin_cage(mesh,arm,profile,voxel_size=.006,binding_pose='CURRENT'):
    """Build in the requested pose; REST avoids welding posed limb contacts.

    Rest binding still needs dynamic face-interior checks: skin proximity at
    cage vertices alone cannot detect a membrane stretched between body parts.
    """
    if binding_pose not in ('CURRENT','REST'):raise ValueError('binding_pose must be CURRENT or REST')
    previous=arm.data.pose_position
    try:
        if binding_pose=='REST':arm.data.pose_position='REST';bpy.context.view_layer.update()
        cage,metadata=_build_skin_cage_in_pose(mesh,arm,profile,voxel_size,rest_pose=binding_pose=='REST')
    finally:
        arm.data.pose_position=previous;bpy.context.view_layer.update()
    metadata['binding_pose']=binding_pose
    return cage,metadata


def _build_skin_cage_in_pose(mesh,arm,profile,voxel_size,rest_pose=False):
    if profile.get('units_to_m',1.)!=1.:raise ValueError('Cage experiment requires metre world coordinates')
    arm_mods=[m for m in mesh.modifiers if m.type=='ARMATURE' and m.show_viewport]
    if len(arm_mods)!=1 or arm_mods[0].use_deform_preserve_volume:raise ValueError('Cage inverse binding currently supports plain LBS only')
    co=coords(mesh);mesh.data.calc_loop_triangles();attr=mesh.data.attributes[profile['surface_attribute']]
    triangles=[tuple(t.vertices) for t in mesh.data.loop_triangles if attr.data[t.polygon_index].value in profile['body_classes']+profile['head_classes']]
    ids=sorted({i for t in triangles for i in t});lookup={i:j for j,i in enumerate(ids)}
    data=bpy.data.meshes.new('ContactSkinCage');data.from_pydata(co[ids].tolist(),[],[tuple(lookup[i] for i in t) for t in triangles]);cage=bpy.data.objects.new('ContactSkinCage',data);bpy.context.scene.collection.objects.link(cage)
    bpy.ops.object.select_all(action='DESELECT');cage.select_set(True);bpy.context.view_layer.objects.active=cage
    remesh=cage.modifiers.new('Watertight skin union','REMESH');remesh.mode='VOXEL';remesh.voxel_size=voxel_size;remesh.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=remesh.name);posed=np.array([v.co[:] for v in cage.data.vertices]);edgecount=Counter(tuple(sorted((a,b))) for p in cage.data.polygons for a,b in zip(p.vertices,list(p.vertices[1:])+[p.vertices[0]]))
    boundary=sum(n!=2 for n in edgecount.values())
    if boundary:raise RuntimeError('Voxel cage is not closed: '+str(boundary))
    tree=BVHTree.FromPolygons(co.tolist(),triangles,all_triangles=True);groups={g.index:g.name for g in mesh.vertex_groups if g.name in arm.data.bones and arm.data.bones[g.name].use_deform};weights=[{groups[g.group]:g.weight for g in v.groups if g.group in groups and g.weight>1e-7} for v in mesh.data.vertices];basis=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    matrices={n:np.eye(4) if rest_pose else np.array(arm.matrix_world@arm.pose.bones[n].matrix@arm.data.bones[n].matrix_local.inverted()@arm.matrix_world.inverted()) for n in set(groups.values())};newweights=[];transforms=[];distances=[]
    for point in posed:
        q,n,index,d=tree.find_nearest(Vector(point));tri=triangles[index];bary=np.maximum(np.array(barycentric_transform(q,*[Vector(co[i]) for i in tri],*basis)),0);bary/=bary.sum();w={}
        for i,factor in zip(tri,bary):
            for name,value in weights[i].items():w[name]=w.get(name,0.)+value*factor
        w={name:value for name,value in w.items() if value>1e-6};total=sum(w.values())
        if total<1e-8:raise ValueError('Skin cage point has no deform-bone weights')
        w={name:value/total for name,value in w.items()};newweights.append(w);transforms.append(sum(matrices[name]*value for name,value in w.items()));distances.append(d)
    transforms=np.array(transforms);rest=np.linalg.solve(transforms,np.c_[posed,np.ones(len(posed))][...,None])[...,0][:,:3];cage.data.vertices.foreach_set('co',rest.astype(np.float32).ravel())
    vgroups={name:cage.vertex_groups.new(name=name) for name in {name for w in newweights for name in w}}
    for i,w in enumerate(newweights):
        for name,value in w.items():vgroups[name].add([i],float(value),'REPLACE')
    deform=cage.modifiers.new('Source animation / inverse pose bound','ARMATURE');deform.object=arm;bpy.context.view_layer.update();error=float(np.max(np.abs(coords(cage)-posed)))
    if error>2e-5:raise RuntimeError('Skin cage inverse binding failed: '+str(error))
    cage.hide_render=True;cage.hide_set(True)
    return cage,{'method':'voxel union + closest triangle weight transfer + inverse evaluated LBS pose binding','voxel_size_m':voxel_size,'vertices':len(posed),'polygons':len(cage.data.polygons),'nonmanifold_edges':boundary,'initial_pose_binding_error_m':error,'initial_source_distance_max_m':float(max(distances)),'initial_source_distance_p99_m':float(np.percentile(distances,99)),'stable_topology':True,'source_mesh_changed':False}


def audit_skin_cage(mesh,cage,profile,sample_budget=12000):
    """Sample visible-skin distance at vertices AND face/edge interiors.

    A fused contact can have accurate vertices but invent a stretched membrane
    when limbs separate. This diagnostic is unsigned and sampled, not a closed
    containment or surface-distance bound.
    """
    if profile.get('units_to_m',1.)!=1.:raise ValueError('Cage audit requires metre world coordinates')
    source=coords(mesh);actual=coords(cage);mesh.data.calc_loop_triangles();attr=mesh.data.attributes[profile['surface_attribute']]
    faces=[tuple(t.vertices) for t in mesh.data.loop_triangles if attr.data[t.polygon_index].value in profile['body_classes']+profile['head_classes']]
    tree=BVHTree.FromPolygons(source.tolist(),faces,all_triangles=True)
    samples={'vertices':actual,
             'face_centres':np.asarray([actual[list(p.vertices)].mean(0) for p in cage.data.polygons]),
             'edge_midpoints':np.asarray([actual[list(e.vertices)].mean(0) for e in cage.data.edges])}
    result={}
    for kind,points in samples.items():
        stride=max(1,int(np.ceil(len(points)/sample_budget)));indices=np.arange(0,len(points),stride);distances=np.array([tree.find_nearest(Vector(v))[3] for v in points[indices]])
        worst=int(np.argmax(distances));result[kind]={'samples':len(indices),'total':len(points),'stride':stride,'unsigned_distance_peak_m':float(distances.max()),'unsigned_distance_p99_m':float(np.percentile(distances,99)),'samples_above_2cm':int(np.sum(distances>.02)),'worst_index':int(indices[worst]),'worst_point':points[indices[worst]].tolist()}
    return {'frame':float(bpy.context.scene.frame_current_final),'surface_distance_bound_proven':False,'samples':result}
