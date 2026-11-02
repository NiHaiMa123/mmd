"""A fitted inner sleeve beneath the original decorative cuff and frill."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform


def install(cloth,body,arm,margin=.0025,skin=None):
    if skin is None:
        from .skin_collision import collider
        skin=collider(body)
    names={g.index:g.name for g in body.vertex_groups};axes={s:(arm.data.bones['腕.'+s].head_local.copy(),arm.data.bones['ひじ.'+s].head_local.copy()) for s in ('L','R')};eligible=set()
    for v in body.data.vertices:
        side='L' if v.co.x>0 else 'R';a,b=axes[side];axis=(b-a).normalized();t=(v.co-a).dot(axis)/(b-a).length;radial=(v.co-a-axis*(v.co-a).dot(axis)).length
        weight=sum(g.weight for g in v.groups if names[g.group].endswith('.'+side) and names[g.group].startswith(('腕','肩')))
        if .10<t<.68 and radial<.065 and weight>.25:eligible.add(v.index)
    chosen=[f for f in body.data.polygons if body.data.materials[f.material_index].mmd_material.name_j=='Body' and all(i in eligible for i in f.vertices)]
    if not chosen:raise ValueError('No target upper-arm surface for sleeve lining')
    mask=body.data.attributes.new('OutfitSleeveLiningFaces','BOOLEAN','FACE')
    for f in chosen:mask.data[f.index].value=True
    audit=body.data.attributes.new('OutfitSleeveLiningAuditFaces','BOOLEAN','FACE')
    for f in chosen:
        p=f.center;side='L' if p.x>0 else 'R';a,b=axes[side];t=(p-a).dot((b-a).normalized())/(b-a).length;audit.data[f.index].value=.20<t<.55
    cloth.data.calc_loop_triangles();tri=[t for t in cloth.data.loop_triangles if cloth.data.materials[t.material_index].mmd_material.name_j=='新規'];points=[v.co.copy() for v in cloth.data.vertices];tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in tri],all_triangles=True);uv=cloth.data.uv_layers.active;design=body.data.attributes.new('OutfitSleeveLiningUV','FLOAT_VECTOR','CORNER')
    for f in chosen:
        for li in f.loop_indices:
            p=body.data.vertices[body.data.loops[li].vertex_index].co;hit,_,ti,_=tree.find_nearest(p);t=tri[ti];design.data[li].vector=barycentric_transform(hit,*(points[i] for i in t.vertices),*(Vector((*uv.data[i].uv,0)) for i in t.loops))
    material=next(m for m in cloth.data.materials if m.mmd_material.name_j=='新規').copy();material.name='Keqing_FittedSleeveLining';material.mmd_material.name_j='袖裏';material.mmd_material.alpha=1.
    attr=material.node_tree.nodes.new('ShaderNodeAttribute');attr.attribute_name='OutfitSleeveLiningUV';material.node_tree.links.new(attr.outputs['Vector'],material.node_tree.nodes['mmd_base_tex'].inputs['Vector'])
    shader=material.node_tree.nodes.get('mmd_shader')
    if shader:
        for name in ('Alpha','Base Alpha'):
            for link in list(shader.inputs[name].links):material.node_tree.links.remove(link)
            shader.inputs[name].default_value=1.
    # The lining uses plain fabric, keeping printed patterns on the outer cuff.
    fabric=material.node_tree.nodes.new('ShaderNodeRGB');fabric.outputs[0].default_value=(.055,.024,.11,1.)
    base=material.node_tree.nodes['mmd_base_tex']
    for link in list(base.outputs['Color'].links):material.node_tree.links.new(fabric.outputs[0],link.to_socket)
    obj=bpy.data.objects.new('SleeveLining',bpy.data.meshes.new('SleeveLining'));bpy.context.scene.collection.objects.link(obj);obj.parent=body.parent;obj.matrix_world=body.matrix_world.copy();obj['mmd_garment']=True;obj['native_only']=True;obj.data.materials.append(material)
    nt=bpy.data.node_groups.new('Outfit_FittedSleeveLining','GeometryNodeTree');nt.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=nt.nodes;l=nt.links;out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=skin;field=n.new('GeometryNodeInputNamedAttribute');field.data_type='BOOLEAN';field.inputs['Name'].default_value='OutfitSleeveLiningFaces'
    normal=n.new('GeometryNodeInputNormal');scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=margin;l.new(normal.outputs[0],scale.inputs[0]);move=n.new('GeometryNodeSetPosition');l.new(info.outputs['Geometry'],move.inputs['Geometry']);l.new(scale.outputs[0],move.inputs['Offset'])
    # Offset using complete skin normals, then trim the sleeve band. Computing
    # normals after trimming biases open boundaries under a deep shoulder bend.
    select=n.new('GeometryNodeSeparateGeometry');select.domain='FACE';l.new(move.outputs['Geometry'],select.inputs['Geometry']);l.new(field.outputs['Attribute'],select.inputs['Selection']);setmat=n.new('GeometryNodeSetMaterial');setmat.inputs['Material'].default_value=material;l.new(select.outputs['Selection'],setmat.inputs['Geometry']);l.new(setmat.outputs['Geometry'],out.inputs['Geometry']);mod=obj.modifiers.new('Fitted upper-arm lining','NODES');mod.node_group=nt;body.data.update();body.update_tag(refresh={'DATA'})
    thickness=obj.modifiers.new('Sleeve lining thickness','SOLIDIFY');thickness.thickness=margin*2;thickness.offset=-1.;thickness.use_even_offset=True
    return obj,{'method':'post-skinning fitted upper-arm lining beneath decorative sleeves','source_faces':len(chosen),'margin_m':margin,'thickness_m':margin*2,'body_geometry_removed':False,'portable_to_pmx':False}
