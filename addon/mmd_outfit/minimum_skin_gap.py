"""Keep near-skin cloth points at a minimum gap without collapsing loose cloth."""
import bpy


def install(garment,skin,region,gap=.004,influence=.025):
    tree=bpy.data.node_groups.new('Outfit_MinimumSkinGap','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n=tree.nodes;l=tree.links
    input_=n.new('NodeGroupInput');out=n.new('NodeGroupOutput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=skin;pos=n.new('GeometryNodeInputPosition');normal=n.new('GeometryNodeInputNormal')
    samples=[]
    for value in (pos.outputs[0],normal.outputs[0]):
        sample=n.new('GeometryNodeSampleNearestSurface');sample.data_type='FLOAT_VECTOR';l.new(info.outputs['Geometry'],sample.inputs['Mesh']);l.new(value,sample.inputs['Value']);l.new(pos.outputs[0],sample.inputs['Sample Position']);samples.append(sample.outputs['Value'])
    hit,norm=samples;normalize=n.new('ShaderNodeVectorMath');normalize.operation='NORMALIZE';l.new(norm,normalize.inputs[0]);norm=normalize.outputs[0]
    delta=n.new('ShaderNodeVectorMath');delta.operation='SUBTRACT';l.new(pos.outputs[0],delta.inputs[0]);l.new(hit,delta.inputs[1]);length=n.new('ShaderNodeVectorMath');length.operation='LENGTH';l.new(delta.outputs[0],length.inputs[0]);dot=n.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT';l.new(delta.outputs[0],dot.inputs[0]);l.new(norm,dot.inputs[1])
    masks=[]
    for field,limit in ((length.outputs['Value'],influence),(dot.outputs['Value'],gap)):
        less=n.new('ShaderNodeMath');less.operation='LESS_THAN';l.new(field,less.inputs[0]);less.inputs[1].default_value=limit;masks.append(less.outputs[0])
    attr=n.new('GeometryNodeInputNamedAttribute');attr.data_type='FLOAT';attr.inputs['Name'].default_value=region;mask=attr.outputs['Attribute']
    for value in masks:
        mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY';l.new(mask,mult.inputs[0]);l.new(value,mult.inputs[1]);mask=mult.outputs[0]
    scale=n.new('ShaderNodeVectorMath');scale.operation='SCALE';l.new(norm,scale.inputs[0]);scale.inputs['Scale'].default_value=gap;add=n.new('ShaderNodeVectorMath');add.operation='ADD';l.new(hit,add.inputs[0]);l.new(scale.outputs[0],add.inputs[1])
    set_=n.new('GeometryNodeSetPosition');l.new(input_.outputs['Geometry'],set_.inputs['Geometry']);l.new(mask,set_.inputs['Selection']);l.new(add.outputs[0],set_.inputs['Position']);l.new(set_.outputs['Geometry'],out.inputs['Geometry']);mod=garment.modifiers.new('Minimum gap at sleeve contact','NODES');mod.node_group=tree
    return {'method':'nearest skin gap in a local influence band','gap_m':gap,'influence_m':influence,'portable_to_pmx':False}
