"""Finite-width native cloth envelope and volume deformation of display hair.

The author supplies the bundle's legal initial surface and attachment weights.
No collision-free or shape-preservation guarantee is implied by setup success.
"""
from collections import defaultdict
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from .surface import coords
from .exact_skin_collider import build_exact_skin_topology
from .native_hair_surface import new_tree,named


def _attach(obj,arm,bone,anchor_target=None):
    c=obj.constraints.new('COPY_TRANSFORMS');c.target=anchor_target or arm;c.subtarget='' if anchor_target else bone;c.target_space='WORLD';c.owner_space='WORLD'


def simulation_anchor(arm,bone,scale):
    """Head motion in centered, independently scaled simulation coordinates."""
    if not 1<=scale<=100:raise ValueError('Simulation scale must be between 1 and 100')
    follow=bpy.data.objects.new('HairProxy_SourceHeadReference',None);bpy.context.scene.collection.objects.link(follow);_attach(follow,arm,bone);bpy.context.view_layer.update()
    origin=np.array(follow.matrix_world.translation,dtype=float)
    delta=bpy.data.objects.new('HairProxy_HeadMotionFromRest',None);bpy.context.scene.collection.objects.link(delta);delta.parent=follow;delta.matrix_parent_inverse=follow.matrix_world.inverted();bpy.context.view_layer.update()
    anchor=bpy.data.objects.new('HairProxy_ScaledSimulationAnchor',None);bpy.context.scene.collection.objects.link(anchor)
    for index,axis in enumerate('XYZ'):
        driver=anchor.driver_add('location',index).driver;variable=driver.variables.new();variable.name='head_location';variable.type='TRANSFORMS';variable.targets[0].id=follow;variable.targets[0].transform_type='LOC_'+axis;variable.targets[0].transform_space='WORLD_SPACE';driver.expression=f'(head_location - {origin[index]:.17g}) * {float(scale):.17g}'
    rotation=anchor.constraints.new('COPY_ROTATION');rotation.target=delta;rotation.target_space='WORLD';rotation.owner_space='WORLD';size=anchor.constraints.new('COPY_SCALE');size.target=delta;size.target_space='WORLD';size.owner_space='WORLD';follow.hide_render=True;delta.hide_render=True;anchor.hide_render=True;bpy.context.view_layer.update()
    return anchor,follow,origin


def build_loft_proxy(world_positions,triangles,pin_weights,arm,bone,rings=25,sides=12,margin=.001,anchor_target=None,attachment_mode='authored',volume_struts=False):
    """Clean closed envelope for overlapping stylized display hair.

    Parallel PCA slices avoid importing display-card intersections into the
    physics topology. The proxy is a single clump: branch motion is not solved.
    """
    points=np.asarray(world_positions,dtype=float);weights=np.asarray(pin_weights,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or weights.shape!=(len(points),) or not np.all(np.isfinite(points)) or not np.all(np.isfinite(weights)) or np.any(weights<0) or np.any(weights>1):raise ValueError('Explicit finite surface and [0,1] attachment weights required')
    if rings<4 or sides<6 or margin<=0 or not np.any(weights>.999):raise ValueError('Provide a resolved clump with hard roots and a usable envelope resolution')
    if attachment_mode not in ('authored','root_only'):raise ValueError('Unknown physical attachment policy')
    origin=points.mean(0);_,_,axes=np.linalg.svd(points-origin,full_matrices=False);axis=axes[0]
    if np.dot(points.mean(0)-points[weights>.999].mean(0),axis)<0:axis=-axis
    u=axes[1];v=np.cross(axis,u);xyz=np.c_[(points-origin)@u,(points-origin)@v,(points-origin)@axis];levels=np.linspace(xyz[:,2].min()-margin,xyz[:,2].max()+margin,rings);spacing=levels[1]-levels[0];angles=np.arange(sides)*2*np.pi/sides;normals=np.c_[np.cos(angles),np.sin(angles)];vertices=[];proxy_weights=[];supports=[]
    for k,z in enumerate(levels):
        near=np.flatnonzero(np.abs(xyz[:,2]-z)<=spacing*1.05)
        if len(near)<3:near=np.argsort(np.abs(xyz[:,2]-z))[:6]
        support=np.max(xyz[near,:2]@normals.T,axis=0)+margin;supports.append(support)
        for j in range(sides):
            xy=np.linalg.solve(normals[[j,(j+1)%sides]],support[[j,(j+1)%sides]]);vertices.append(origin+u*xy[0]+v*xy[1]+axis*z);proxy_weights.append(1. if k==0 else float(np.mean(weights[near])))
    faces=[]
    for k in range(rings-1):
        for j in range(sides):
            a=k*sides+j;b=k*sides+(j+1)%sides;c=(k+1)*sides+(j+1)%sides;d=(k+1)*sides+j;faces.extend([(a,b,c),(a,c,d)])
    for k in (0,rings-1):
        center=len(vertices);vertices.append(np.mean(vertices[k*sides:(k+1)*sides],axis=0));proxy_weights.append(1. if k==0 else 0.)
        for j in range(sides):faces.append((center,k*sides+(j+1)%sides,k*sides+j) if k==0 else (center,k*sides+j,k*sides+(j+1)%sides))
    if attachment_mode=='root_only':proxy_weights=[1. if w>.999 else 0. for w in proxy_weights]
    proxy_world=np.asarray(vertices);bm=bmesh.new();vv=[bm.verts.new(p) for p in proxy_world]
    for f in faces:bm.faces.new([vv[i] for i in f])
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.verts.ensure_lookup_table();bm.verts.index_update();faces=[tuple(v.index for v in f.verts) for f in bm.faces];bm.free();own=BVHTree.FromPolygons(proxy_world.tolist(),faces,all_triangles=True);self_pairs=[(a,b) for a,b in own.overlap(own) if a<b and not set(faces[a])&set(faces[b])]
    if self_pairs:raise ValueError('Constructed envelope intersects itself')
    # Exact halfspace interpolation for this convex-section ruled loft avoids
    # coordinate-dependent ray parity when checking its known construction.
    supports=np.asarray(supports);lower=np.clip(np.searchsorted(levels,xyz[:,2],side='right')-1,0,rings-2);fraction=(xyz[:,2]-levels[lower])/spacing;limits=supports[lower]*(1-fraction[:,None])+supports[lower+1]*fraction[:,None];violation=float(np.max(xyz[:,:2]@normals.T-limits))
    if violation>1e-7:raise ValueError('Loft does not cover the display hair; split or adapt the clump')
    struts=[]
    if volume_struts:
        if sides%2:raise ValueError('Volume struts require an even section resolution')
        for k in range(rings):
            for j in range(sides//2):struts.append((k*sides+j,k*sides+j+sides//2))
        for k in range(rings-1):
            for j in range(sides):struts.append((k*sides+j,(k+1)*sides+(j+sides//2)%sides))
    head=np.array(anchor_target.matrix_world if anchor_target else arm.matrix_world@arm.pose.bones[bone].matrix);inverse=np.linalg.inv(head);data=bpy.data.meshes.new('HairProxy_CleanEnvelope');data.from_pydata((proxy_world@inverse[:3,:3].T+inverse[:3,3]).tolist(),struts,faces);data.update();proxy=bpy.data.objects.new('HairProxy_CleanPhysicalEnvelope',data);bpy.context.scene.collection.objects.link(proxy);_attach(proxy,arm,bone,anchor_target);pin=proxy.vertex_groups.new(name='HairProxy_Attachment')
    for i,w in enumerate(proxy_weights):
        if w>0:pin.add([i],w,'REPLACE')
    _,representatives,source_to_display=np.unique(np.rint(points/(margin*.001)).astype(np.int64),axis=0,return_index=True,return_inverse=True);display_points=points[representatives];display_weights=weights[representatives]
    low=np.full(len(display_points),np.inf);high=np.full(len(display_points),-np.inf);np.minimum.at(low,source_to_display,weights);np.maximum.at(high,source_to_display,weights)
    if np.max(high-low)>1e-4:raise ValueError('Coincident display points have incompatible attachment weights')
    display_faces=np.asarray(source_to_display[np.asarray(triangles,dtype=int)]);display_data=bpy.data.meshes.new('HairProxy_DisplayRest');display_data.from_pydata((display_points@inverse[:3,:3].T+inverse[:3,3]).tolist(),[],display_faces.tolist());display_data.update();display=bpy.data.objects.new('HairProxy_DrivenDisplay',display_data);bpy.context.scene.collection.objects.link(display);display['HairProxy_SourceToDisplay']=source_to_display.tolist();_attach(display,arm,bone,anchor_target);soft=display.vertex_groups.new(name='HairProxy_DisplayFlexible')
    for i,w in enumerate(display_weights):
        if w<=.999:soft.add([i],float(1-w) if attachment_mode=='authored' else 1.,'REPLACE')
    bpy.context.view_layer.update();surf=display.modifiers.new('Native Mesh Deform from clean volume cage','MESH_DEFORM');surf.object=proxy;surf.precision=6;surf.vertex_group=soft.name;bpy.ops.object.select_all(action='DESELECT');display.select_set(True);bpy.context.view_layer.objects.active=display;bpy.ops.object.meshdeform_bind(modifier=surf.name)
    if not surf.is_bound:raise RuntimeError('Native volume Mesh Deform binding failed')
    anchors=set(np.flatnonzero(display_weights>.999).tolist());best=np.full(len(display_points),np.inf)
    for i in anchors:best=np.minimum(best,np.linalg.norm(display_points-display_points[i],axis=1))
    while len(anchors)<min(72,len(display_points)):
        i=int(np.argmax(best));anchors.add(i);best=np.minimum(best,np.linalg.norm(display_points-display_points[i],axis=1))
    anchor_group=display.vertex_groups.new(name='HairProxy_RestDetailAnchors');anchor_group.add(sorted(anchors),1.,'REPLACE');smooth=display.modifiers.new('Native Laplacian rest-shape reconstruction','LAPLACIANDEFORM');smooth.vertex_group=anchor_group.name;smooth.iterations=12;bpy.ops.object.laplaciandeform_bind(modifier=smooth.name);hard_attr=display_data.attributes.new('HairProxy_ExactRootMask','BOOLEAN','POINT');hard_attr.data.foreach_set('value',(display_weights>.999));rest_attr=display_data.attributes.new('HairProxy_RigidRestPosition','FLOAT_VECTOR','POINT');rest_buffer=np.empty(len(display_data.vertices)*3,dtype=np.float32);display_data.vertices.foreach_get('co',rest_buffer);rest_attr.data.foreach_set('vector',rest_buffer);root_tree,root_in,root_out=new_tree('HairProxy_ExactRigidAttachment');root_set=root_tree.nodes.new('GeometryNodeSetPosition');root_tree.links.new(root_in.outputs['Geometry'],root_set.inputs['Geometry']);root_tree.links.new(named(root_tree,'HairProxy_ExactRootMask','BOOLEAN'),root_set.inputs['Selection']);root_tree.links.new(named(root_tree,'HairProxy_RigidRestPosition','FLOAT_VECTOR'),root_set.inputs['Position']);root_tree.links.new(root_set.outputs['Geometry'],root_out.inputs['Geometry']);root_mod=display.modifiers.new('Exact authored rigid roots','NODES');root_mod.node_group=root_tree;bpy.context.view_layer.update();error=float(np.max(np.abs(coords(display)[source_to_display]-points)))
    if error>margin*.01:raise RuntimeError(f'Envelope binding changed the rest shape beyond 1% of envelope padding: {error}')
    proxy.hide_render=True;display.hide_render=True
    return proxy,display,{'method':'parallel PCA slices / circumscribed convex section loft','attachment_mode':attachment_mode,'explicit_internal_struts':len(struts),'original_skinning_weights_edited':False,'proxy_vertices':len(vertices),'proxy_faces':len(faces),'display_vertices':len(points),'boundary_edges':0,'nonmanifold_edges_above_two_faces':0,'initial_nonadjacent_proxy_intersections':len(self_pairs),'maximum_section_halfspace_violation_sim_units':violation,'rest_surface_deform_error_sim_units':error,'hard_root_count':sum(w>.999 for w in proxy_weights),'partial_attachment_count':sum(0<w<=.999 for w in proxy_weights),'display_hard_roots_excluded_from_deformer':int((weights>.999).sum()),'rings':rings,'sides':sides,'envelope_margin_sim_units':margin,'branch_motion_independently_solved':False,'binding':'Blender native Mesh Deform + Laplacian rest-shape reconstruction','detail_anchor_count':len(anchors),'welded_display_vertices':len(display_points)}


def build_proxy(world_positions,triangles,pin_weights,arm,bone,weld_distance=1e-6):
    points=np.asarray(world_positions,dtype=float);triangles=np.asarray(triangles,dtype=int);weights=np.asarray(pin_weights,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or weights.shape!=(len(points),) or not np.all(np.isfinite(points)) or not np.all(np.isfinite(weights)) or np.any(weights<0) or np.any(weights>1):raise ValueError('Explicit finite positions and attachment weights in [0,1] required')
    if bone not in arm.pose.bones or weld_distance<=0:raise ValueError('Explicit anchor and positive weld distance required')
    bm=bmesh.new();verts=[bm.verts.new(p) for p in points]
    for f in triangles:
        try:bm.faces.new([verts[i] for i in f])
        except ValueError:raise ValueError('Duplicate proxy input triangle')
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=weld_distance);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=weld_distance*.01);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if any(len(e.link_faces)>2 for e in bm.edges):bm.free();raise ValueError('Proxy weld creates nonmanifold edges; adapt selection explicitly')
    bm.verts.ensure_lookup_table();bm.verts.index_update();proxy_world=np.array([v.co[:] for v in bm.verts]);faces=[tuple(v.index for v in f.verts) for f in bm.faces];boundary=sum(e.is_boundary for e in bm.edges);bm.free()
    own=BVHTree.FromPolygons(proxy_world.tolist(),faces,all_triangles=True);self_pairs=[(a,b) for a,b in own.overlap(own) if a<b and not set(faces[a])&set(faces[b])]
    if self_pairs:raise ValueError(f'Physical surface has {len(self_pairs)} nonadjacent initial intersections; construct a clean envelope instead')
    tree=KDTree(len(points))
    for i,p in enumerate(points):tree.insert(p,i)
    tree.balance();proxy_weights=[];spread=0.
    for p in proxy_world:
        near=tree.find_range(p,weld_distance*1.1);values=[weights[i] for q,i,d in near]
        if not values:raise ValueError('Welded proxy has no source correspondence')
        spread=max(spread,max(values)-min(values));proxy_weights.append(float(np.mean(values)))
    if spread>1e-4:raise ValueError('Coincident seam vertices have incompatible attachment weights')
    proxy_weights=np.asarray(proxy_weights);head=np.array(arm.matrix_world@arm.pose.bones[bone].matrix);inverse=np.linalg.inv(head);local=proxy_world@inverse[:3,:3].T+inverse[:3,3];data=bpy.data.meshes.new('HairProxy_WeldedSurface');data.from_pydata(local.tolist(),[],faces);data.update();proxy=bpy.data.objects.new('HairProxy_PhysicalSurface',data);bpy.context.scene.collection.objects.link(proxy);_attach(proxy,arm,bone);pin=proxy.vertex_groups.new(name='HairProxy_Attachment')
    for i,w in enumerate(proxy_weights):
        if w>0:pin.add([i],float(w),'REPLACE')
    # A detached island cannot be rescued by a root on a different island.
    neighbors=defaultdict(set)
    for edge in data.edges:
        a,b=edge.vertices;neighbors[a].add(b);neighbors[b].add(a)
    remaining=set(range(len(local)));islands=[]
    while remaining:
        stack=[remaining.pop()];island=[]
        while stack:
            i=stack.pop();island.append(i)
            for j in neighbors[i]:
                if j in remaining:remaining.remove(j);stack.append(j)
        hard=int(np.sum(proxy_weights[island]>.999));islands.append({'vertices':len(island),'hard_roots':hard})
        if hard<2:raise ValueError('Every physical island needs at least two hard attachment vertices')
    display_data=bpy.data.meshes.new('HairProxy_DisplayRest');display_data.from_pydata((points@inverse[:3,:3].T+inverse[:3,3]).tolist(),[],triangles.tolist());display_data.update();display=bpy.data.objects.new('HairProxy_DrivenDisplay',display_data);bpy.context.scene.collection.objects.link(display);_attach(display,arm,bone);proxy.hide_render=True;display.hide_render=True;bpy.context.view_layer.update()
    surf=display.modifiers.new('Native Surface Deform from physical proxy','SURFACE_DEFORM');surf.target=proxy;surf.falloff=4.;bpy.ops.object.select_all(action='DESELECT');display.select_set(True);bpy.context.view_layer.objects.active=display;bpy.ops.object.surfacedeform_bind(modifier=surf.name)
    if not surf.is_bound:raise RuntimeError('Native Surface Deform failed to bind')
    error=float(np.max(np.abs(coords(display)-points)))
    if error>2e-5:raise RuntimeError('Proxy binding changed the legal rest surface')
    return proxy,display,{'proxy_vertices':len(local),'proxy_faces':len(faces),'display_vertices':len(points),'boundary_edges':boundary,'nonmanifold_edges_above_two_faces':0,'attachment_weight_seam_spread':spread,'islands':islands,'rest_surface_deform_error_m':error,'initial_nonadjacent_proxy_intersections':len(self_pairs),'initial_self_pair_examples':self_pairs[:12],'weld_distance_m':weld_distance,'binding':'Blender native Surface Deform','hard_root_count':int((proxy_weights>.999).sum()),'partial_attachment_count':int(((proxy_weights>0)&(proxy_weights<=.999)).sum())}


def live_skin_collider(mesh,arm,profile,simulation_scale=1.,simulation_origin=None):
    origin=np.zeros(3) if simulation_origin is None else np.asarray(simulation_origin,dtype=float)
    ids,faces,metadata=build_exact_skin_topology(mesh,arm,profile,triangulate=True);positions=coords(mesh);data=bpy.data.meshes.new('HairProxy_ExactSkin');data.from_pydata(((positions[ids]-origin)*simulation_scale).tolist(),[],faces);data.update();obj=bpy.data.objects.new('HairProxy_LiveSkinCollider',data);bpy.context.scene.collection.objects.link(obj);attr=data.attributes.new('HairProxy_SkinSourceIndex','INT','POINT');attr.data.foreach_set('value',ids.astype(np.int32));tree,inp,out=new_tree('HairProxy_ExactAnimatedSkin');links=tree.links;info=tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=mesh;sample=tree.nodes.new('GeometryNodeSampleIndex');sample.data_type='FLOAT_VECTOR';sample.domain='POINT';position=tree.nodes.new('GeometryNodeInputPosition');links.new(info.outputs['Geometry'],sample.inputs['Geometry']);links.new(position.outputs['Position'],sample.inputs['Value']);links.new(named(tree,'HairProxy_SkinSourceIndex','INT'),sample.inputs['Index']);shift=tree.nodes.new('ShaderNodeVectorMath');shift.operation='SUBTRACT';shift.inputs[1].default_value=origin;links.new(sample.outputs['Value'],shift.inputs[0]);scale=tree.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs[3].default_value=simulation_scale;links.new(shift.outputs['Vector'],scale.inputs[0]);setpos=tree.nodes.new('GeometryNodeSetPosition');links.new(inp.outputs['Geometry'],setpos.inputs['Geometry']);links.new(scale.outputs['Vector'],setpos.inputs['Position']);links.new(setpos.outputs['Geometry'],out.inputs['Geometry']);deform=obj.modifiers.new('Exact source skin deformation','NODES');deform.node_group=tree;obj.modifiers.new('Native cloth collision','COLLISION');obj.collision.thickness_outer=.002*simulation_scale;obj.collision.thickness_inner=.001*simulation_scale;obj.collision.damping_factor=.5
    if hasattr(obj.collision,'use_culling'):obj.collision.use_culling=False
    obj.hide_render=True;bpy.context.view_layer.update();error=float(np.max(np.abs(coords(obj)/simulation_scale+origin-positions[ids])))
    if error>2e-5:raise RuntimeError('Live collider differs from source skin')
    return obj,ids,dict(metadata,initial_source_position_error_m=error)


def configure_dynamics(proxy,collider,first,last,*,quality=20,self_collision=True,body_collision=True,bending=3.,mass=5e-5,simulation_scale=1.):
    if any(m.type=='CLOTH' for m in proxy.modifiers):raise ValueError('Proxy already has a cloth solver')
    sim=proxy.modifiers.new('Native finite-width hair dynamics','CLOTH');s=sim.settings;s.quality=quality;s.mass=mass;s.air_damping=3.;s.tension_stiffness=1000.;s.compression_stiffness=1000.;s.shear_stiffness=500.;s.bending_stiffness=bending;s.bending_model='ANGULAR';s.tension_damping=10.;s.compression_damping=10.;s.shear_damping=10.;s.bending_damping=5.;s.vertex_group_mass='HairProxy_Attachment';s.pin_stiffness=50.;s.use_dynamic_mesh=False;s.use_internal_springs=True;s.internal_spring_max_length=.06*simulation_scale;s.internal_tension_stiffness=500.;s.internal_compression_stiffness=500.;s.effector_weights.gravity=simulation_scale
    world=coords(proxy);shortest=float(min(np.linalg.norm(world[e.vertices[0]]-world[e.vertices[1]]) for e in proxy.data.edges));self_margin=min(.0005*simulation_scale,shortest*.2)
    c=sim.collision_settings;c.use_collision=body_collision;c.collision_quality=8;c.distance_min=.00075*simulation_scale;c.use_self_collision=self_collision;c.self_distance_min=self_margin;c.self_friction=1.;c.impulse_clamp=.05*simulation_scale;c.self_impulse_clamp=.05*simulation_scale;collider.collision.thickness_outer=.00075*simulation_scale;collection=bpy.data.collections.new('HairProxy_OnlyActualSkinColliders');bpy.context.scene.collection.children.link(collection);collection.objects.link(collider);c.collection=collection;sim.point_cache.frame_start=first;sim.point_cache.frame_end=last
    if self_collision and abs(c.self_distance_min-self_margin)>1e-6:raise ValueError('Native collision minimum exceeds the proxy feature scale; use a larger independent simulation scale')
    return sim,{'backend':'Blender native CLOTH surface + internal springs','simulation_scale':simulation_scale,'quality':quality,'vertex_mass_kg':mass,'estimated_total_mass_kg':mass*len(proxy.data.vertices),'stretch_stiffness':s.tension_stiffness,'shear_stiffness':s.shear_stiffness,'angular_bending_stiffness_sim_units':s.bending_stiffness,'pin_stiffness':s.pin_stiffness,'internal_springs':True,'body_collision':c.use_collision,'self_collision':c.use_self_collision,'cloth_contact_margin_m':c.distance_min/simulation_scale,'collider_contact_margin_m':collider.collision.thickness_outer/simulation_scale,'self_contact_margin_m':c.self_distance_min/simulation_scale,'minimum_rest_edge_m':shortest/simulation_scale,'collision_impulse_clamp_model_units_per_frame':c.impulse_clamp/simulation_scale,'self_impulse_clamp_model_units_per_frame':c.self_impulse_clamp/simulation_scale,'gravity_weight':s.effector_weights.gravity,'air_damping':s.air_damping,'frames':[first,last]}


def display_positions_world(display):
    positions=coords(display)
    mapping=display.get('HairProxy_SourceToDisplay')
    return positions if mapping is None else positions[np.asarray(mapping,dtype=int)]
