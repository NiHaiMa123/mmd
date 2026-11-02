"""A post-skinning hosiery surface, with the checked feet kept verbatim.

The entire source skin surface remains present in the body object. The nylon
is a separate material/geometry shell sampled from its evaluated pose.
"""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


def install(stock,body,bindings,foot_ids,margin=.0025,waist=1.065):
    foot_ids=set(foot_ids);mesh=stock.data;body_mesh=body.data
    foot_map={b[0][0]:k for k,b in enumerate(bindings) if len(b)==1 and b[0][0] in foot_ids}
    assert len(foot_map)==len(foot_ids)
    def attribute(data,name,kind,domain):return data.attributes.get(name) or data.attributes.new(name,kind,domain)
    faces=attribute(body_mesh,'OutfitNylonFaces','BOOLEAN','FACE');foot=attribute(body_mesh,'OutfitNylonFoot','BOOLEAN','POINT');indices=attribute(body_mesh,'OutfitNylonFootIndex','INT','POINT')
    audit=attribute(body_mesh,'OutfitAudit_TightsHipRegion','FLOAT','POINT');own_audit=attribute(mesh,'OutfitAudit_TightsHipRegion','FLOAT','POINT')
    for v,d in zip(body_mesh.vertices,audit.data):d.value=float(v.co.z>.78)
    for v,d in zip(mesh.vertices,own_audit.data):d.value=float(v.co.z>.78)
    for v in body_mesh.vertices:
        foot.data[v.index].value=v.index in foot_map;indices.data[v.index].value=foot_map.get(v.index,0)
    body_count=0
    for f in body_mesh.polygons:
        include=body_mesh.materials[f.material_index].mmd_material.name_j in {'Body','Nails'} and f.center.z<waist and abs(f.center.x)<.205 and not all(i in foot_ids for i in f.vertices)
        faces.data[f.index].value=include;body_count+=include
    preserve=attribute(mesh,'OutfitNylonPreserveFoot','BOOLEAN','FACE')
    for f in mesh.polygons:preserve.data[f.index].value=all(len(bindings[i])==1 and bindings[i][0][0] in foot_ids for i in f.vertices)
    # Assign a rest-space design field without changing the body's UV layers.
    mesh.calc_loop_triangles();pts=[v.co.copy() for v in mesh.vertices];tri=list(mesh.loop_triangles);uv=mesh.uv_layers.active
    tree=BVHTree.FromPolygons(pts,[tuple(t.vertices) for t in tri],all_triangles=True)
    design=attribute(body_mesh,'OutfitNylonUV','FLOAT_VECTOR','CORNER');own=attribute(mesh,'OutfitNylonUV','FLOAT_VECTOR','CORNER')
    for loop,d in zip(mesh.loops,own.data):d.vector=(*uv.data[loop.index].uv,0.)
    for loop in body_mesh.loops:
        p=body_mesh.vertices[loop.vertex_index].co;hit,_,ti,_=tree.find_nearest(p);t=tri[ti]
        design.data[loop.index].vector=barycentric_transform(hit,*(pts[i] for i in t.vertices),*(Vector((*uv.data[i].uv,0)) for i in t.loops))
    area=attribute(body_mesh,'tights_design_area','FLOAT','POINT')
    for v,d in zip(body_mesh.vertices,area.data):p=v.co;d.value=max(0.,min(1.,(.88-p.z)/.03))*max(0.,min(1.,(p.z-.22)/.04)) if p.x>.035 else 0.
    material=mesh.materials[0];nodes=material.node_tree.nodes;links=material.node_tree.links;uvnode=nodes.new('ShaderNodeAttribute');uvnode.attribute_name='OutfitNylonUV';links.new(uvnode.outputs['Vector'],nodes['StockingGoldMask'].inputs['Vector'])
    nt=bpy.data.node_groups.new('Outfit_LiveNylonShell','GeometryNodeTree');nt.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');nt.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=nt.nodes;l=nt.links
    input_=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=body
    def field(name,kind='BOOLEAN'):
        a=n.new('GeometryNodeInputNamedAttribute');a.data_type=kind;a.inputs['Name'].default_value=name;return a.outputs['Attribute']
    def separate(geometry,selection):
        node=n.new('GeometryNodeSeparateGeometry');node.domain='FACE';l.new(geometry,node.inputs['Geometry']);l.new(selection,node.inputs['Selection']);return node.outputs['Selection']
    skin=separate(info.outputs['Geometry'],field('OutfitNylonFaces'))
    # UV seams are disconnected in the PMX skin. Weld the live upper surface
    # before computing its normals, while retaining the exact foot-ring IDs.
    weld=n.new('GeometryNodeMergeByDistance');weld.inputs['Distance'].default_value=.00005;l.new(skin,weld.inputs['Geometry']);not_foot=n.new('FunctionNodeBooleanMath');not_foot.operation='NOT';l.new(field('OutfitNylonFoot'),not_foot.inputs[0]);l.new(not_foot.outputs[0],weld.inputs['Selection']);skin=weld.outputs['Geometry']
    normal=n.new('GeometryNodeInputNormal');position=n.new('GeometryNodeInputPosition');offset=n.new('ShaderNodeVectorMath');offset.operation='SCALE';l.new(normal.outputs[0],offset.inputs[0]);offset.inputs['Scale'].default_value=margin
    move=n.new('GeometryNodeSetPosition');l.new(skin,move.inputs['Geometry']);l.new(offset.outputs[0],move.inputs['Offset'])
    # Shared ankle-ring positions use the exact evaluated foot patch, making
    # the new upper shell meet the old checked shoe fit without a weld guess.
    sample=n.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';l.new(input_.outputs['Geometry'],sample.inputs['Geometry']);l.new(position.outputs[0],sample.inputs['Value']);l.new(field('OutfitNylonFootIndex','INT'),sample.inputs['Index'])
    seam=n.new('GeometryNodeSetPosition');l.new(move.outputs['Geometry'],seam.inputs['Geometry']);l.new(field('OutfitNylonFoot'),seam.inputs['Selection']);l.new(sample.outputs['Value'],seam.inputs['Position'])
    setmat=n.new('GeometryNodeSetMaterial');setmat.inputs['Material'].default_value=material;l.new(seam.outputs['Geometry'],setmat.inputs['Geometry'])
    join=n.new('GeometryNodeJoinGeometry');l.new(setmat.outputs['Geometry'],join.inputs['Geometry']);l.new(separate(input_.outputs['Geometry'],field('OutfitNylonPreserveFoot')),join.inputs['Geometry'])
    # A smooth opaque gusset covers the source's anatomical interior surfaces.
    if 'OutfitGussetFaces' in mesh.attributes:
        gusset=separate(input_.outputs['Geometry'],field('OutfitGussetFaces'));blur=n.new('GeometryNodeBlurAttribute');blur.data_type='FLOAT_VECTOR';blur.inputs['Iterations'].default_value=4;l.new(position.outputs[0],blur.inputs['Value']);smooth=n.new('GeometryNodeSetPosition');l.new(gusset,smooth.inputs['Geometry']);l.new(blur.outputs['Value'],smooth.inputs['Position']);l.new(smooth.outputs['Geometry'],join.inputs['Geometry'])
    l.new(join.outputs['Geometry'],out.inputs['Geometry']);mod=stock.modifiers.new('Nylon from evaluated body surface','NODES');mod.node_group=nt
    # Never expose the old broad gusset patch or copy internal anatomical
    # islands into clothing. Keep the underlying body's geometry unchanged.
    from .hosiery_cleanup import clean
    cleanup=clean(body,stock)
    body_mesh.update();body.update_tag(refresh={'DATA'})
    return {'method':'complete evaluated skin shell plus preserved foot patch','skin_faces':body_count-cleanup['internal_faces_excluded_from_nylon'],'foot_vertices':len(foot_map),'margin_m':margin,'body_geometry_removed':False,'hosiery_cleanup':cleanup,'portable_to_pmx':False}
