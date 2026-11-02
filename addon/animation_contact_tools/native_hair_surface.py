"""Blender 5.2 native XPBD cloth-surface backend for polygonal MMD hair.

Experimental: preserves original topology via an explicit welded simulation
mesh and index mapping. Original animation and mesh rest positions stay intact.
"""
from pathlib import Path
import numpy as np
import bpy,bmesh
from .surface import coords

ASSET='geometry_nodes_dynamics_assets.blend'

def asset_path():
    if not hasattr(bpy.types,'GeometryNodeXPBDSolver'):raise RuntimeError('Native XPBD node unavailable in this Blender build')
    candidates=[Path(bpy.utils.resource_path(kind))/'datafiles/assets/nodes'/ASSET for kind in ('LOCAL','SYSTEM')]
    return next((p for p in candidates if p.is_file()),None)

def new_tree(name):
    tree=bpy.data.node_groups.new(name,'GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
    return tree,tree.nodes.new('NodeGroupInput'),tree.nodes.new('NodeGroupOutput')

def named(tree,name,kind='FLOAT'):
    node=tree.nodes.new('GeometryNodeInputNamedAttribute');node.data_type=kind;node.inputs['Name'].default_value=name;return node.outputs['Attribute']

def group(tree,data):node=tree.nodes.new('GeometryNodeGroup');node.node_tree=data;return node

def integer_compare(tree,links,value,operation,threshold):
    node=tree.nodes.new('FunctionNodeCompare');node.data_type='INT';node.operation=operation
    a=next(s for s in node.inputs if s.name=='A' and s.type=='INT');b=next(s for s in node.inputs if s.name=='B' and s.type=='INT');b.default_value=threshold;links.new(value,a);return node.outputs[0]

def build_native_hair_surface(mesh,arm,profile,parts,substeps=8,iterations=20,pin_threshold=.999,margin=.001,zero_mass_pins=False,embedded_root_pins=False,head_local=False,split_colliders=False):
    asset=asset_path()
    if asset is None:raise RuntimeError('Blender native dynamics asset was not found')
    with bpy.data.libraries.load(str(asset),link=False) as (source,dest):dest.node_groups=['Cloth Dynamics (Experimental)','Collider']
    cloth_group,collider_group=dest.node_groups
    # A reference copy keeps the pre-contact deformation graph. Main geometry
    # reads the simulator; simulator reads only this reference, never main.
    reference=mesh.copy();reference.name='HairContact_SourceReference';bpy.context.scene.collection.objects.link(reference);reference.hide_render=True;reference.hide_set(True)
    faces=parts['faces']['hair_root']+parts['faces']['hair_mobile'];hairids=sorted({i for f in faces for i in f});local=np.array([v.co[:] for v in mesh.data.vertices]);rest=local[hairids]
    _,first,inverse=np.unique(np.rint(rest*profile.get('units_to_m',1.)*1e6).astype(np.int64),axis=0,return_index=True,return_inverse=True);representatives=np.array(hairids)[first];mapping=dict(zip(hairids,inverse.tolist()));simfaces=[tuple(mapping[i] for i in f) for f in faces];simfaces=[f for f in simfaces if len(set(f))==3]
    data=bpy.data.meshes.new('HairContact_WeldedSurface');data.from_pydata(local[representatives].tolist(),[],simfaces);sim=bpy.data.objects.new('HairContact_XPBD_Surface',data);bpy.context.scene.collection.objects.link(sim);sim.matrix_world=mesh.matrix_world.copy();sim.hide_render=True;sim.hide_set(True)
    original=data.attributes.new('HairSourceVertex','INT','POINT');original.data.foreach_set('value',representatives.astype(np.int32));pin=data.attributes.new('HairRootPin','FLOAT','POINT')
    anchors={mesh.vertex_groups[n].index for n in profile.get('root_hair_anchor_bones',[]) if n in mesh.vertex_groups};headweights=np.array([sum(g.weight for g in mesh.data.vertices[i].groups if g.group in anchors) for i in hairids]);pinweights=np.ones(len(first),dtype=np.float32)
    np.minimum.at(pinweights,inverse,headweights);pinweights=(pinweights>=pin_threshold).astype(np.float32);pin.data.foreach_set('value',pinweights)
    embedded=np.zeros(len(first),dtype=bool)
    if embedded_root_pins:
        world=coords(mesh)*profile.get('units_to_m',1.);bm=bmesh.new()
        for co in world[parts['ids']['head']]:bm.verts.new(co)
        bmesh.ops.convex_hull(bm,input=list(bm.verts));bm.normal_update();planes=[(np.array(f.normal),np.array(f.verts[0].co)) for f in bm.faces];embedded[:]=True
        for normal,origin in planes:embedded&=((world[representatives]-origin)@normal<=.0002)
        bm.free();pinweights[embedded]=1.;pin.data.foreach_set('value',pinweights)
    if head_local:
        anchor=profile.get('hair_coordinate_bone')
        if anchor not in arm.pose.bones:raise ValueError('head_local requires an explicit hair_coordinate_bone')
        current_world=sim.matrix_world.copy();sim.parent=arm;sim.parent_type='BONE';sim.parent_bone=anchor;bpy.context.view_layer.update();sim.matrix_world=current_world;bpy.context.view_layer.update()
    index_attr=mesh.data.attributes.get('HairContactSimIndex') or mesh.data.attributes.new('HairContactSimIndex','INT','POINT');indices=np.full(len(mesh.data.vertices),-1,dtype=np.int32);indices[hairids]=inverse;index_attr.data.foreach_set('value',indices)
    tree,inp,out=new_tree('HairContact_NativeXPBD');links=tree.links;ref=tree.nodes.new('GeometryNodeObjectInfo');ref.transform_space='RELATIVE';ref.inputs['Object'].default_value=reference
    sampler=tree.nodes.new('GeometryNodeSampleIndex');sampler.data_type='FLOAT_VECTOR';sampler.domain='POINT';links.new(ref.outputs['Geometry'],sampler.inputs['Geometry']);position=tree.nodes.new('GeometryNodeInputPosition');links.new(position.outputs['Position'],sampler.inputs['Value']);links.new(named(tree,'HairSourceVertex','INT'),sampler.inputs['Index'])
    setpos=tree.nodes.new('GeometryNodeSetPosition');links.new(inp.outputs['Geometry'],setpos.inputs['Geometry']);links.new(sampler.outputs['Value'],setpos.inputs['Position'])
    # Full skin collider, including head. Fixed follicle overlap is audited
    # explicitly; no wholesale exclusion of head-weighted hair from detection.
    cls=named(tree,profile['surface_attribute'],'INT');skin_classes=profile['body_classes']+profile['head_classes'];selection=integer_compare(tree,links,cls,'EQUAL',skin_classes[0])
    for value in skin_classes[1:]:
        include=integer_compare(tree,links,cls,'EQUAL',value);both=tree.nodes.new('FunctionNodeBooleanMath');both.operation='OR';links.new(selection,both.inputs[0]);links.new(include,both.inputs[1]);selection=both.outputs[0]
    selections=[('BodyCollider',selection)]
    if split_colliders:
        region_attr=mesh.data.attributes.get('HairBodyRegion') or mesh.data.attributes.new('HairBodyRegion','INT','FACE');values=np.zeros(len(mesh.data.polygons),dtype=np.int32);selections=[]
        for region_id,region in enumerate(('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'),1):
            values[parts['source_faces'][region]]=region_id
            selections.append((region,integer_compare(tree,links,named(tree,'HairBodyRegion','INT'),'EQUAL',region_id)))
        region_attr.data.foreach_set('value',values)
    effectors=tree.nodes.new('NodeCombineBundle')
    for label,selection in selections:
        skin=tree.nodes.new('GeometryNodeSeparateGeometry');skin.domain='FACE';links.new(ref.outputs['Geometry'],skin.inputs['Geometry']);links.new(selection,skin.inputs['Selection'])
        collider=group(tree,collider_group);collider.inputs['Deforming'].default_value=True;collider.inputs['Edge Contacts'].default_value=True;collider.inputs['Margin'].default_value=margin;links.new(skin.outputs['Selection'],collider.inputs['Geometry'])
        label=label.replace('.','_');item=effectors.bundle_items.new('BUNDLE',label);links.new(collider.outputs['Collider'],effectors.inputs[item.name])
    cloth=group(tree,cloth_group);links.new(setpos.outputs['Geometry'],cloth.inputs['Geometry']);links.new(named(tree,'HairRootPin'),cloth.inputs['Pin Group']);links.new(effectors.outputs[0],cloth.inputs['Effectors'])
    cloth.inputs['Stretchiness'].default_value=0.;cloth.inputs['Bendiness'].default_value=.025;cloth.inputs['Substeps'].default_value=substeps;cloth.inputs['Constraint Steps'].default_value=iterations;cloth.inputs['Collision Radius'].default_value=.001;cloth.inputs['Linear Damping'].default_value=3.;cloth.inputs['Mass'].default_value=.01
    if zero_mass_pins:
        mass=tree.nodes.new('ShaderNodeMath');mass.operation='SUBTRACT';mass.inputs[0].default_value=1.;links.new(named(tree,'HairRootPin'),mass.inputs[1]);scale=tree.nodes.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=.01;links.new(mass.outputs[0],scale.inputs[0]);links.new(scale.outputs[0],cloth.inputs['Mass'])
    next(s for s in cloth.inputs if s.name=='Gravity' and s.type=='BOOLEAN').default_value=False
    self_info=tree.nodes.new('GeometryNodeObjectInfo');self_info.inputs['Object'].default_value=sim;links.new(self_info.outputs['Transform'],cloth.inputs['Simulation to World'])
    links.new(cloth.outputs['Geometry'],out.inputs['Geometry']);modifier=sim.modifiers.new('Native XPBD hair surface','NODES');modifier.node_group=tree
    # Sample deformation back onto the original geometry, keeping its UVs,
    # shape-key ordering, material indices and every non-hair point unchanged.
    mapping_tree,main_in,main_out=new_tree('HairContact_ApplyWeldedSurface');ml=mapping_tree.links;info=mapping_tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=sim
    sample=mapping_tree.nodes.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';ml.new(info.outputs['Geometry'],sample.inputs['Geometry']);pos=mapping_tree.nodes.new('GeometryNodeInputPosition');ml.new(pos.outputs['Position'],sample.inputs['Value']);idx=named(mapping_tree,'HairContactSimIndex','INT');ml.new(idx,sample.inputs['Index'])
    valid=integer_compare(mapping_tree,ml,idx,'GREATER_EQUAL',0);apply=mapping_tree.nodes.new('GeometryNodeSetPosition');ml.new(main_in.outputs['Geometry'],apply.inputs['Geometry']);ml.new(valid,apply.inputs['Selection']);ml.new(sample.outputs['Value'],apply.inputs['Position']);ml.new(apply.outputs['Geometry'],main_out.inputs['Geometry']);main_modifier=mesh.modifiers.new('Hair contact surface (experimental)','NODES');main_modifier.node_group=mapping_tree
    return {'reference':reference,'simulator':sim,'main_modifier':main_modifier,'simulation_modifier':modifier,'metadata':{'backend':'Blender native XPBD / welded polygonal surface','source_hair_vertices':len(hairids),'simulated_vertices':len(first),'welded_triangles':len(simfaces),'pinned_vertices':int(pinweights.sum()),'embedded_root_candidates':int(embedded.sum()),'substeps':substeps,'iterations':iterations,'margin_m':margin,'surface_self_collision':False,'gravity':False,'zero_mass_pins':zero_mass_pins,'head_local':head_local,'split_colliders':split_colliders,'asset_path':str(asset)},'hairids':hairids,'indices':inverse,'pinweights':pinweights,'representatives':representatives}
