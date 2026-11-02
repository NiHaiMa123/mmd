"""Closed anatomical collider parts, cut from a REST-bound skin cage.

Native XPBD supports only one point contact per point per collider. Separate
closed parts allow concurrent head/torso/limb contacts without treating open
semantic skin patches as solids. Joint caps are internal approximation surfaces.
"""
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .surface import coords


def split_rest_cage(mesh,arm,cage,profile,parts):
    previous=arm.data.pose_position
    try:
        arm.data.pose_position='REST';bpy.context.view_layer.update()
        source=coords(mesh);rest=coords(cage);mesh.data.calc_loop_triangles();attr=mesh.data.attributes[profile['surface_attribute']]
        roles={pi:role for role,polys in parts['source_faces'].items() if not role.startswith('hair') for pi in polys}
        triangles=[t for t in mesh.data.loop_triangles if attr.data[t.polygon_index].value in profile['body_classes']+profile['head_classes']]
        tree=BVHTree.FromPolygons(source.tolist(),[tuple(t.vertices) for t in triangles],all_triangles=True);groups={}
        for face in cage.data.polygons:
            centre=rest[list(face.vertices)].mean(0);_,_,index,_=tree.find_nearest(Vector(centre));role=roles.get(triangles[index].polygon_index)
            if role is None:raise ValueError('A skin cage face has no semantic source region')
            groups.setdefault(role,[]).append(tuple(face.vertices))
        results=[];metadata=[];source_weights=[[(cage.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in cage.data.vertices]
        for role,faces in sorted(groups.items()):
            ids=sorted({i for f in faces for i in f});lookup={i:j for j,i in enumerate(ids)};data=bpy.data.meshes.new('ClosedSkin_'+role);data.from_pydata(rest[ids].tolist(),[],[tuple(lookup[i] for i in f) for f in faces]);before=len(data.polygons)
            bm=bmesh.new();bm.from_mesh(data);boundary=[e for e in bm.edges if e.is_boundary];filled=bmesh.ops.holes_fill(bm,edges=boundary,sides=0) if boundary else {'faces':[]};caps=len(filled['faces']);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));nonmanifold=sum(not e.is_manifold for e in bm.edges)
            if nonmanifold:bm.free();raise RuntimeError(f'Anatomical collider {role} is not closed: {nonmanifold} edges')
            bm.to_mesh(data);bm.free()
            if len(data.vertices)!=len(ids):raise RuntimeError('Joint cap creation changed the vertex map')
            obj=bpy.data.objects.new('ClosedSkin_'+role,data);bpy.context.scene.collection.objects.link(obj)
            vertex_groups={name:obj.vertex_groups.new(name=name) for name in {n for i in ids for n,w in source_weights[i]}}
            for j,i in enumerate(ids):
                for name,w in source_weights[i]:vertex_groups[name].add([j],w,'REPLACE')
            mod=obj.modifiers.new('Source LBS / rest cage part','ARMATURE');mod.object=arm;obj.hide_render=True;obj.hide_set(True);results.append(obj)
            metadata.append({'role':role,'object':obj.name,'vertices':len(ids),'source_faces':before,'joint_cap_faces':caps,'nonmanifold_edges':nonmanifold})
        return results,{'method':'REST-bound cage cut by nearest semantic skin face; joint boundaries capped','parts':metadata,'joint_caps_are_approximation':True,'requires_dynamic_validation':True,'accepted':False,'self_collision_proven':False}
    finally:
        arm.data.pose_position=previous;bpy.context.view_layer.update()
