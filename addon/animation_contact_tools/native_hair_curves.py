"""Adapter to Blender's bundled Hair Dynamics asset, with explicit curve input.

Experimental: independent curves only. A curve pass does not certify a mapped
polygonal hair card, its width, or hair-to-hair self-contact.
"""
import bpy
from .native_hair_surface import asset_path,new_tree,group


def attach_curve_dynamics(hair,colliders,substeps=20,iterations=30,gravity=False,bendiness=.25,root_bendiness=.2,collision_margin=.001):
    if hair.type!='CURVES':raise ValueError('Native hair dynamics requires a CURVES object')
    if hair.data.surface is None:raise ValueError('Hair requires an explicit attachment surface')
    asset=asset_path()
    if asset is None:raise RuntimeError('Bundled native dynamics asset not found')
    with bpy.data.libraries.load(str(asset),link=False) as (source,dest):
        dest.node_groups=['Hair Dynamics','Collider']
    hair_group,collider_group=dest.node_groups
    tree,inp,out=new_tree('HairContact_NativeCurveDynamics');links=tree.links
    dynamics=group(tree,hair_group);dynamics.inputs['Mode'].default_value='Physics (Experimental)'
    dynamics.inputs['Substeps'].default_value=substeps;dynamics.inputs['Constraint Steps'].default_value=iterations
    dynamics.inputs['Stretchiness'].default_value=0.;dynamics.inputs['Bendiness'].default_value=bendiness
    dynamics.inputs['Root Bendiness'].default_value=root_bendiness
    next(s for s in dynamics.inputs if s.name=='Gravity' and s.type=='BOOLEAN').default_value=gravity
    bundle=tree.nodes.new('NodeCombineBundle')
    for i,obj in enumerate(colliders):
        info=tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=obj
        collider=group(tree,collider_group);links.new(info.outputs['Geometry'],collider.inputs['Geometry'])
        collider.inputs['Deforming'].default_value=True;collider.inputs['Edge Contacts'].default_value=True
        collider.inputs['Margin'].default_value=collision_margin;collider.inputs['Friction'].default_value=.2
        item=bundle.bundle_items.new('BUNDLE','Collider'+str(i));links.new(collider.outputs['Collider'],bundle.inputs[item.name])
    if colliders:links.new(bundle.outputs['Bundle'],dynamics.inputs['Effectors'])
    links.new(inp.outputs['Geometry'],dynamics.inputs['Hair']);links.new(dynamics.outputs['Hair'],out.inputs['Geometry'])
    modifier=hair.modifiers.new('Native hair curve collision experiment','NODES');modifier.node_group=tree
    return modifier,{'backend':'Blender bundled Hair Dynamics / XPBD curves','asset':str(asset),
        'mode':str(dynamics.inputs['Mode'].default_value),'substeps':substeps,'iterations':iterations,
        'colliders':[o.name for o in colliders],'gravity':gravity,'bendiness':bendiness,'root_bendiness':root_bendiness,'edge_contacts':True,'margin_m':collision_margin,
        'self_contact_tested':False}


def curve_positions_world(hair):
    import numpy as np
    ev=hair.evaluated_get(bpy.context.evaluated_depsgraph_get());co=np.empty(len(ev.data.points)*3,dtype=np.float32)
    ev.data.points.foreach_get('position',co);co=co.reshape(-1,3);m=np.asarray(ev.matrix_world)
    return co@m[:3,:3].T+m[:3,3]
