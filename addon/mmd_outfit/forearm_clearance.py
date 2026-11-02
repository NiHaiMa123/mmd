"""Pose-driven capsule clearance for upper-arm frills and hanging sleeves."""
import bpy
from mathutils import Vector


def install(cloth,body,arm,region='OutfitAudit_SleeveRegion',margin=.004):
    names={g.index:g.name for g in body.vertex_groups};plans=[]
    for side in ('L','R'):
        elbow='ひじ.'+side;wrist='手首.'+side;a=arm.data.bones[elbow].head_local;b=arm.data.bones[wrist].head_local;axis=(b-a).normalized();length=(b-a).length;radii=[]
        for v in body.data.vertices:
            weight=sum(g.weight for g in v.groups if names[g.group].endswith('.'+side) and names[g.group].startswith(('ひじ','手捩')))
            t=(v.co-a).dot(axis)
            if weight>.5 and .02<t<length-.005:radii.append((v.co-a-axis*t).length)
        if not radii:raise ValueError('Missing forearm surface '+side)
        radius=max(radii)*1.08+margin;anchors=[]
        for bone in (elbow,wrist):
            obj=bpy.data.objects.new('OutfitCollider_'+bone,None);bpy.context.scene.collection.objects.link(obj);obj['outfit_backup']=True;obj.hide_render=True;obj.hide_set(True)
            constraint=obj.constraints.new('COPY_LOCATION');constraint.target=arm;constraint.subtarget=bone;constraint.head_tail=0.;anchors.append(obj)
        plans.append((side,radius,anchors))
    tree=bpy.data.node_groups.new('Outfit_ForearmCapsules','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=tree.nodes;l=tree.links;input_=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');geometry=input_.outputs['Geometry']
    def vec(op,a,b=None):
        node=n.new('ShaderNodeVectorMath');node.operation=op;l.new(a,node.inputs[0])
        if b is not None:l.new(b,node.inputs[1])
        return node.outputs['Value'] if op in ('DOT_PRODUCT','LENGTH') else node.outputs['Vector']
    for side,radius,anchors in plans:
        infos=[]
        for obj in anchors:
            info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=obj;infos.append(info.outputs['Location'])
        position=n.new('GeometryNodeInputPosition');a,b=infos;axis=vec('SUBTRACT',b,a);delta=vec('SUBTRACT',position.outputs[0],a);numerator=vec('DOT_PRODUCT',delta,axis);denominator=vec('DOT_PRODUCT',axis,axis)
        divide=n.new('ShaderNodeMath');divide.operation='DIVIDE';l.new(numerator,divide.inputs[0]);l.new(denominator,divide.inputs[1]);clamp=n.new('ShaderNodeClamp');l.new(divide.outputs[0],clamp.inputs['Value'])
        scaled=n.new('ShaderNodeVectorMath');scaled.operation='SCALE';l.new(axis,scaled.inputs[0]);l.new(clamp.outputs[0],scaled.inputs['Scale']);center=vec('ADD',a,scaled.outputs[0]);radial=vec('SUBTRACT',position.outputs[0],center);distance=vec('LENGTH',radial)
        inside=n.new('ShaderNodeMath');inside.operation='LESS_THAN';l.new(distance,inside.inputs[0]);inside.inputs[1].default_value=radius
        attr=n.new('GeometryNodeInputNamedAttribute');attr.data_type='FLOAT';attr.inputs['Name'].default_value=region;mask=n.new('ShaderNodeMath');mask.operation='MULTIPLY';l.new(attr.outputs['Attribute'],mask.inputs[0]);l.new(inside.outputs[0],mask.inputs[1])
        normal=vec('NORMALIZE',radial);offset=n.new('ShaderNodeVectorMath');offset.operation='SCALE';l.new(normal,offset.inputs[0]);offset.inputs['Scale'].default_value=radius
        set_=n.new('GeometryNodeSetPosition');l.new(geometry,set_.inputs['Geometry']);l.new(mask.outputs[0],set_.inputs['Selection']);l.new(vec('ADD',center,offset.outputs[0]),set_.inputs['Position']);geometry=set_.outputs['Geometry']
    l.new(geometry,out.inputs['Geometry']);mod=cloth.modifiers.new('Sleeve clearance around moving forearms','NODES');mod.node_group=tree
    return {'method':'pose-driven forearm capsules','radii_m':{s:r for s,r,_ in plans},'margin_m':margin,'portable_to_pmx':False}
