"""Native Blender correction after skinning, with a live skin-only collider.

This is a Blender modifier feature; PMX cannot encode its per-frame surface
projection. It complements the sleeve chains, rather than replacing dynamics.
"""
import bpy


def collider(body):
    mesh=bpy.data.meshes.new('SkinCollisionSource');proxy=bpy.data.objects.new('Outfit_SkinCollider',mesh);bpy.context.scene.collection.objects.link(proxy)
    proxy.hide_render=True;proxy.hide_set(True);proxy['outfit_backup']=True;proxy['outfit_collider']=True
    proxy['outfit_skin_source']=body.name
    tree=bpy.data.node_groups.new('Outfit_LiveBodySkin','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    nodes=tree.nodes;links=tree.links;out=nodes.new('NodeGroupOutput');info=nodes.new('GeometryNodeObjectInfo');info.inputs['Object'].default_value=body;info.transform_space='RELATIVE'
    index=nodes.new('GeometryNodeInputMaterialIndex');compare=nodes.new('FunctionNodeCompare');compare.data_type='INT';compare.operation='NOT_EQUAL'
    integer_inputs=[s for s in compare.inputs if s.bl_idname=='NodeSocketInt'];integer_inputs[1].default_value=next(i for i,m in enumerate(body.data.materials) if m.mmd_material.name_j=='Body');links.new(index.outputs[0],integer_inputs[0])
    delete=nodes.new('GeometryNodeDeleteGeometry');delete.domain='FACE';delete.mode='ALL';links.new(info.outputs['Geometry'],delete.inputs['Geometry']);links.new(compare.outputs['Result'],delete.inputs['Selection'])
    weld=nodes.new('GeometryNodeMergeByDistance');weld.inputs['Distance'].default_value=.00005;links.new(delete.outputs['Geometry'],weld.inputs['Geometry']);links.new(weld.outputs['Geometry'],out.inputs['Geometry'])
    modifier=proxy.modifiers.new('Live skin surface','NODES');modifier.node_group=tree
    return proxy


def install(obj,proxy,ids,group_name='OutfitCollision',offset=.0018,subdivision=1):
    ids=list(ids);group=obj.vertex_groups.get(group_name) or obj.vertex_groups.new(name=group_name);group.add(ids,1.,'REPLACE')
    # Vertex groups occupy an attribute name too; use a separate audit name.
    attr=obj.data.attributes.new('OutfitAudit_'+group_name,'FLOAT','POINT')
    for i in ids:attr.data[i].value=1.
    if subdivision:
        sub=obj.modifiers.new('Surface samples for cloth contact','SUBSURF');sub.subdivision_type='SIMPLE';sub.levels=subdivision;sub.render_levels=subdivision
        if hasattr(sub,'use_custom_normals'):sub.use_custom_normals=True
    shrink=obj.modifiers.new('Keep clothing outside posed skin','SHRINKWRAP');shrink.target=proxy;shrink.vertex_group=group.name;shrink.wrap_method='NEAREST_SURFACEPOINT';shrink.wrap_mode='OUTSIDE';shrink.offset=offset
    return {'method':'post-skinning outside-only surface correction','target':proxy.name,'vertex_group':group.name,'vertices':len(ids),'subdivision':subdivision,'offset_m':offset,'portable_to_pmx':False}
