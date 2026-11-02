"""Independent animated skin collider for a controlled Bullet backend test.

Bake before building physics: an Armature modifier here would introduce a
dependency cycle through the hair's physics-driven bones. This is experimental;
the skin's open neck boundary is reported rather than silently capped.
"""
import struct
from pathlib import Path
from collections import Counter
import bpy
import numpy as np
from .surface import coords


def bake_body_surface(mesh, profile, directory, start=1, end=450):
    if abs(float(profile.get('units_to_m',1.))-1.)>1e-9:raise ValueError('Bullet body-surface experiment currently requires metre world coordinates')
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    mesh.data.calc_loop_triangles();attr=mesh.data.attributes[profile['surface_attribute']]
    faces=[tuple(t.vertices) for t in mesh.data.loop_triangles
           if attr.data[t.polygon_index].value in profile['body_classes']]
    if not faces:raise ValueError('Body-only surface classification is required')
    ids=sorted({i for f in faces for i in f});lookup={i:j for j,i in enumerate(ids)}
    topology=[tuple(lookup[i] for i in f) for f in faces]
    cache=directory/'AnimatedBodySkin.pc2';scene=bpy.context.scene;old=scene.frame_current
    with cache.open('wb') as handle:
        handle.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,len(ids),0.,1.,end-start+1))
        for frame in range(start,end+1):
            scene.frame_set(frame);bpy.context.view_layer.update()
            co=coords(mesh)[ids].astype('<f4');handle.write(co.tobytes())
            if frame==start:initial=co.copy()
    data=bpy.data.meshes.new('HairContact_AnimatedSkinSurface');data.from_pydata(initial.tolist(),[],topology)
    obj=bpy.data.objects.new('HairContact_IndependentBodyCollider',data);scene.collection.objects.link(obj)
    mod=obj.modifiers.new('Baked source skin / no hair dependency','MESH_CACHE')
    mod.cache_format='PC2';mod.filepath=str(cache);mod.play_mode='SCENE';mod.time_mode='FRAME'
    mod.frame_start=start;mod.frame_scale=1.;mod.deform_mode='OVERWRITE';mod.interpolation='LINEAR'
    obj.hide_render=True;obj.display_type='WIRE'
    errors=[]
    for frame in sorted({start,end,(start+end)//2}):
        scene.frame_set(frame);bpy.context.view_layer.update()
        errors.append(float(np.max(np.abs(coords(obj)-coords(mesh)[ids]))))
    scene.frame_set(old);bpy.context.view_layer.update()
    if max(errors)>2e-6:raise RuntimeError('Independent body cache does not match source skin')
    edges=Counter(tuple(sorted((a,b))) for f in topology for a,b in zip(f,(f[1],f[2],f[0])))
    return obj,{'cache':str(cache),'vertices':len(ids),'triangles':len(topology),
                'cache_check_max_error_m':max(errors),'topological_boundary_edges':sum(n==1 for n in edges.values()),
                'scope':'body_classes only; head/root embedding remains separately audited',
                'dependency':'PC2 only; no Armature modifier or physics-dependent driver'}


def enable_body_surface(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=obj;bpy.ops.rigidbody.object_add()
    rigid=obj.rigid_body;rigid.type='PASSIVE';rigid.kinematic=True;rigid.collision_shape='MESH'
    rigid.mesh_source='FINAL';rigid.use_deform=True;rigid.use_margin=True;rigid.collision_margin=.001
    rigid.friction=.3;rigid.restitution=0.
    return {'type':rigid.type,'kinematic':rigid.kinematic,'shape':rigid.collision_shape,
            'mesh_source':rigid.mesh_source,'deforming_mesh':rigid.use_deform,'margin_m':rigid.collision_margin}
