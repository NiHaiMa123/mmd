"""Bounded visual attachment for stable sleeves.

bind_clamped_frames is used by the delivered rotation/strain correction.
The private physical-solver installer is a rejected experimental comparison;
its parameter changes alone did not solve the supplied animation.
"""
import bpy,bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .structured_cloth import _tree,_field,_info,_sample,_mix_position
from .mesh_cloth import configure


def bind_clamped_frames(carrier,target,rest_mesh,faces,selection):
    """Bounded barycentrics plus a rigid local offset, only on explicit points."""
    rest_mesh.calc_loop_triangles();allowed=set(faces);triangles=[t for t in rest_mesh.loop_triangles if t.polygon_index in allowed];points=[v.co.copy() for v in rest_mesh.vertices];bvh=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True);mesh=carrier.data
    active=mesh.attributes.new('SleeveStableBind','BOOLEAN','POINT');indices=[mesh.attributes.new('SleeveStableI'+str(k),'INT','POINT') for k in range(3)];weights=[mesh.attributes.new('SleeveStableW'+str(k),'FLOAT','POINT') for k in range(3)];offset=mesh.attributes.new('SleeveStableOffset','FLOAT_VECTOR','POINT');largest=0.
    for i in selection:
        v=mesh.vertices[i];hit,_,ti,_=bvh.find_nearest(v.co);tri=triangles[ti];a,b,c=(points[j] for j in tri.vertices);u=(b-a).normalized();normal=(b-a).cross(c-a).normalized();tangent=normal.cross(u).normalized();delta=v.co-hit;w=barycentric_transform(hit,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)));w=Vector([max(0.,min(1.,value)) for value in w]);w/=sum(w)
        active.data[i].value=True;offset.data[i].vector=(delta.dot(u),delta.dot(tangent),delta.dot(normal));largest=max(largest,delta.length)
        for k in range(3):indices[k].data[i].value=tri.vertices[k];weights[k].data[i].value=w[k]
    tree=_tree('Outfit_StableSleeveFrames',True);n,l=tree.nodes,tree.links;inp=n.new('NodeGroupInput');geo=_info(tree,target);samples=[_sample(tree,geo,_field(tree,'SleeveStableI'+str(k),'INT')) for k in range(3)]
    def vec(op,a,b=None):
        node=n.new('ShaderNodeVectorMath');node.operation=op;l.new(a,node.inputs[0])
        if b is not None:l.new(b,node.inputs[1])
        return node.outputs['Vector']
    values=[]
    for k in range(3):
        scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(samples[k],scale.inputs[0]);l.new(_field(tree,'SleeveStableW'+str(k)),scale.inputs['Scale']);values.append(scale.outputs['Vector'])
    position=vec('ADD',vec('ADD',values[0],values[1]),values[2]);edge1=vec('SUBTRACT',samples[1],samples[0]);edge2=vec('SUBTRACT',samples[2],samples[0]);u=vec('NORMALIZE',edge1);normal=vec('NORMALIZE',vec('CROSS_PRODUCT',edge1,edge2));tangent=vec('NORMALIZE',vec('CROSS_PRODUCT',normal,u));separate=n.new('ShaderNodeSeparateXYZ');l.new(_field(tree,'SleeveStableOffset','FLOAT_VECTOR'),separate.inputs[0])
    for axis,direction in zip(('X','Y','Z'),(u,tangent,normal)):
        scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(direction,scale.inputs[0]);l.new(separate.outputs[axis],scale.inputs['Scale']);position=vec('ADD',position,scale.outputs['Vector'])
    move=n.new('GeometryNodeSetPosition');l.new(inp.outputs['Geometry'],move.inputs['Geometry']);l.new(_field(tree,'SleeveStableBind','BOOLEAN'),move.inputs['Selection']);l.new(position,move.inputs['Position']);out=n.new('NodeGroupOutput');l.new(move.outputs['Geometry'],out.inputs['Geometry']);carrier.modifiers.new('Stable clamped sleeve frames','NODES').node_group=tree
    return {'vertices':len(selection),'maximum_local_offset_m':largest,'barycentric_range':[0,1]}


def _install_experimental_solver(proxy,reference,target,carrier,arm,skin,*,bones=('腕.L','腕.R'),quality=24,stiffness=400.,first=1,last=496):
    """Experimental comparison only; not the delivered sleeve repair."""
    if bpy.data.objects.get('StableSleeveSimulationSurface'):raise ValueError('Stable sleeve solver already installed')
    group_indices={proxy.vertex_groups[name].index for name in bones};ids=sorted(v.index for v in proxy.data.vertices if any(g.group in group_indices and g.weight>.5 for g in v.groups));chosen=set(ids);faces=[f.index for f in proxy.data.polygons if all(i in chosen for i in f.vertices)];mapping={old:new for new,old in enumerate(ids)}
    if not faces:raise ValueError('Explicit sleeve bone groups contain no faces')
    mesh=bpy.data.meshes.new('WeldedSleevePhysics');mesh.from_pydata([proxy.data.vertices[i].co[:] for i in ids],[],[[mapping[i] for i in proxy.data.polygons[fi].vertices] for fi in faces]);mesh.update();sleeves=bpy.data.objects.new('StableSleeveSimulationSurface',mesh);bpy.context.scene.collection.objects.link(sleeves);sleeves.matrix_world=proxy.matrix_world.copy();sleeves['outfit_backup']=True
    for g in proxy.vertex_groups:sleeves.vertex_groups.new(name=g.name)
    for old,new in mapping.items():
        for g in proxy.data.vertices[old].groups:sleeves.vertex_groups[g.group].add([new],g.weight,'REPLACE')
    before=len(mesh.vertices);bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update();kd=KDTree(len(mesh.vertices))
    for v in mesh.vertices:kd.insert(v.co,v.index)
    kd.balance();merged_map={}
    for i in ids:
        _,j,d=kd.find(proxy.data.vertices[i].co)
        if d>1e-5:raise ValueError('Welded sleeve correspondence lost')
        merged_map[i]=j
    sleeves.modifiers.new('Coherent sleeve attachment','ARMATURE').object=arm
    # Read only the cached skirt islands from the existing simulation.
    mask=proxy.data.attributes.new('StableSleeveMask','BOOLEAN','POINT')
    for i in ids:mask.data[i].value=True
    collider=bpy.data.objects.new('CachedSkirtSleeveCollider',bpy.data.meshes.new('CachedSkirtCollision'));bpy.context.scene.collection.objects.link(collider);collider.matrix_world=proxy.matrix_world.copy();collider['outfit_backup']=True;tree=_tree('Outfit_CachedSkirtCollision');n,l=tree.nodes,tree.links;separate=n.new('GeometryNodeSeparateGeometry');separate.domain='FACE';l.new(_info(tree,proxy),separate.inputs['Geometry']);l.new(_field(tree,'StableSleeveMask','BOOLEAN'),separate.inputs['Selection']);out=n.new('NodeGroupOutput');l.new(separate.outputs['Inverted'],out.inputs['Geometry']);collider.modifiers.new('Cached skirt geometry','NODES').node_group=tree
    sim,solver=configure(sleeves,'ClothPins',[skin,collider],first=first,last=last);s=sim.settings;s.quality=quality;s.tension_stiffness=stiffness;s.compression_stiffness=stiffness;s.shear_stiffness=stiffness*.5;s.bending_stiffness=9.;s.air_damping=5.;s.tension_damping=20.;s.compression_damping=20.;s.shear_damping=15.;s.bending_damping=8.;s.use_dynamic_mesh=True;sim.collision_settings.collision_quality=10;sim.collision_settings.self_distance_min=.0015;sim.point_cache.name='StableSleeves';sim.point_cache.use_disk_cache=True
    mask=reference.data.attributes.new('StableSleeveMask','BOOLEAN','POINT');indices=reference.data.attributes.new('StableSleeveIndex','INT','POINT')
    for i,j in merged_map.items():mask.data[i].value=True;indices.data[i].value=j
    tree=_tree('Outfit_ActualSleeveCachedSkirtTarget');n,l=tree.nodes,tree.links;index=n.new('GeometryNodeInputIndex').outputs[0];geo=_info(tree,reference);old=_sample(tree,_info(tree,proxy),index);mixed=_mix_position(tree,geo,old,_field(tree,'OutfitClothMotion'));new=_sample(tree,_info(tree,sleeves),_field(tree,'StableSleeveIndex','INT'));move=n.new('GeometryNodeSetPosition');l.new(mixed,move.inputs['Geometry']);l.new(_field(tree,'StableSleeveMask','BOOLEAN'),move.inputs['Selection']);l.new(new,move.inputs['Position']);out=n.new('NodeGroupOutput');l.new(move.outputs['Geometry'],out.inputs['Geometry']);target.modifiers['Controlled cloth displacement'].node_group=tree
    # Update only carrier points that previously belonged to a sleeve triangle.
    attrs=carrier.data.attributes;visual={v.index for v in carrier.data.vertices if all(attrs['OutfitBindI'+str(k)].data[v.index].value in chosen for k in range(3))};binding=bind_clamped_frames(carrier,target,proxy.data,faces,visual)
    for obj in (sleeves,collider):obj.hide_render=True;obj.hide_set(True)
    return sleeves,sim,{'method':'welded real sleeve cloth, no positional reference blend; bounded rigid-frame visual attachment; cached skirts preserved','sleeve_vertices_before_weld':before,'sleeve_vertices_after_weld':len(mesh.vertices),'welded_vertices':before-len(mesh.vertices),'quality':s.quality,'stiffness':s.tension_stiffness,'binding':binding,**solver}
