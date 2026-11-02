"""Stock Cloth in larger simulation coordinates; native local-space relay.

All integration/contact/binding stays in Blender. No per-frame position edits,
geometric collision correction, filtering or custom dynamics are performed.
"""
import argparse,json,sys,shutil
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Matrix
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--out',required=True)
p.add_argument('--scale',type=float,default=10.);p.add_argument('--quality',type=int,default=128)
p.add_argument('--normalise-air-damping',action='store_true')
p.add_argument('--fit-inner-clump',help='Authored clump name for static body-facing proxy fit')
p.add_argument('--inner-offset',type=float,default=.0005)
p.add_argument('--inner-edge-length',type=float,help='Native local subdivision target before static inner fit (metres)')
p.add_argument('--inner-cleanup-distance',type=float,help='Native degenerate dissolve threshold for the fitted free patch')
p.add_argument('--inner-decimate-ratio',type=float,help='Native Edit Mode Decimate restricted to the free fitted patch')
p.add_argument('--static-proxy-asset',help='Verified static proxy NPZ; native dynamics and binding remain unchanged')
p.add_argument('--body-margin-real',type=float,help='Combined proxy/skin contact distance in display metres')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);baseline=Path(a.baseline);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True);assert not (out/'configuration.json').exists(),'Use a fresh directory'
config=json.loads((baseline/'configuration.json').read_text('utf8'));S=a.scale;assert S>1
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=config['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update()
proxy=bpy.data.objects['HairProxy_全头共享几何体积'];anchor=proxy.parent
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
display=bpy.data.objects[s['HairDisplayObject']];body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部']
expected_display=coords(display).copy();expected_proxy=coords(proxy).copy()
old_cloth=next(md for md in proxy.modifiers if md.type=='CLOTH');assert not old_cloth.point_cache.is_baked
assert not old_cloth.point_cache.use_external
def values(rna,allow_pointers=()):
    result={}
    for prop in rna.bl_rna.properties:
        name=prop.identifier
        if name=='rna_type' or prop.is_readonly:continue
        if prop.type=='POINTER' and name not in allow_pointers:continue
        if prop.type=='COLLECTION':continue
        value=getattr(rna,name)
        result[name]=tuple(value) if getattr(prop,'is_array',False) else value
    return result
settings=values(old_cloth.settings);collision_settings=values(old_cloth.collision_settings,('collection',))
effector_settings=values(old_cloth.settings.effector_weights)
body_settings=values(body.collision)
old_cloth.show_viewport=False;old_cloth.show_render=False
path=out/'完整角色_原生Cloth放大模拟_未烘焙.blend'
# Save in the fresh directory before replacing runtime physics modifiers, so
# no operation can target the baseline's automatically named disk-cache folder.
bpy.ops.wm.save_as_mainfile(filepath=str(path))
deform=next(md for md in display.modifiers if md.type=='SURFACE_DEFORM')
bpy.ops.object.select_all(action='DESELECT');display.select_set(True);bpy.context.view_layer.objects.active=display
if deform.is_bound:bpy.ops.object.surfacedeform_bind(modifier=deform.name)
proxy.modifiers.remove(old_cloth)
for md in list(body.modifiers):
    if md.type=='COLLISION':body.modifiers.remove(md)
fit_report=None
static_asset_report=None
if a.static_proxy_asset:
    assert not a.fit_inner_clump,'Prebuilt static asset is already fitted'
    static_asset=Path(a.static_proxy_asset);asset=np.load(static_asset)
    static_asset_report=json.loads((static_asset.parent/'remesh_report.json').read_text('utf8'))
    assert static_asset_report['asset_gate_pass'],'Rejected static proxy asset'
    mesh=bpy.data.meshes.new('Standard_LocalRemesh_StaticProxy')
    mesh.from_pydata(asset['vertices'].tolist(),[],asset['triangles'].tolist());mesh.update()
    proxy.data=mesh;rebuilt_pins=asset['pins'].astype(bool)
    root_group=proxy.vertex_groups.get(settings['vertex_group_mass'])
    if root_group is None:root_group=proxy.vertex_groups.new(name=settings['vertex_group_mass'])
    root_group.add(np.flatnonzero(rebuilt_pins).tolist(),1.,'REPLACE')
    bpy.context.view_layer.update();expected_proxy=coords(proxy).copy()
if a.fit_inner_clump:
    base=ROOT.parent/'work/headswap_xl_codex';inp=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
    meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
    ci=next(i for i,r in enumerate(meta['chains']) if r['name']==a.fit_inner_clump)
    selected_points=inp['world'][inp['chain_labels']==ci]
    clump_tree=KDTree(len(selected_points))
    for i,pnt in enumerate(selected_points):clump_tree.insert(pnt,i)
    clump_tree.balance()
    hard_points=inp['world'][inp['hard'].astype(bool)];hard_tree=KDTree(len(hard_points))
    for i,pnt in enumerate(hard_points):hard_tree.insert(pnt,i)
    hard_tree.balance()
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
    fitdata=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
    skinfit=bpy.data.objects.new('StaticFit_ActualInitialSkin',fitdata);s.collection.objects.link(skinfit);skinfit.matrix_world=body.matrix_world.copy()
    skin_world=coords(skinfit);fitdata.calc_loop_triangles();skin_faces=np.array([t.vertices[:] for t in fitdata.loop_triangles])
    skin_tree=BVHTree.FromPolygons(skin_world.tolist(),skin_faces.tolist(),all_triangles=True)
    original_proxy=coords(proxy).copy()
    original_rest=np.load(baseline/'clump_proxy_rest.npz')
    original_fixed_world=original_proxy[original_rest['pins'].astype(bool)]
    normal_matrix=proxy.matrix_world.to_3x3().inverted().transposed()
    def fit_weight(vertex,pnt):
        closest,normal,_,distance=skin_tree.find_nearest(Vector(pnt))
        toward=closest-Vector(pnt)
        cosine=(normal_matrix@vertex.normal).normalized().dot(toward.normalized()) if toward.length else 0.
        bundle_distance=clump_tree.find(Vector(pnt))[2]
        root_distance=hard_tree.find(Vector(pnt))[2]
        w=float(np.clip((cosine-.1)/.6,0,1)*np.clip((.012-distance)/.006,0,1)*np.clip((.012-bundle_distance)/.006,0,1)*np.clip((root_distance-.02)/.02,0,1))
        return w
    subdivision_report=None
    if a.inner_edge_length:
        assert a.inner_edge_length>=.001,'Avoid excessively fine contact triangles'
        bm=bmesh.new();bm.from_mesh(proxy.data);bm.normal_update()
        rounds=[]
        for iteration in range(4):
            active={v for v in bm.verts if fit_weight(v,proxy.matrix_world@v.co)>.001}
            selected=[e for e in bm.edges if any(v in active for v in e.verts)
                and e.calc_length()>a.inner_edge_length
                and all(hard_tree.find(proxy.matrix_world@v.co)[2]>.02 for v in e.verts)]
            if not selected:break
            rounds.append(dict(iteration=iteration+1,split_edges=len(selected)))
            bmesh.ops.subdivide_edges(bm,edges=selected,cuts=1,smooth=0.,use_grid_fill=True,use_single_edge=True)
            bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
            bm.normal_update()
        bm.to_mesh(proxy.data);bm.free();proxy.data.update();bpy.context.view_layer.update()
        subdivision_report=dict(method='Native BMesh local edge subdivision and beauty triangulation',
            target_edge_length_m=a.inner_edge_length,rounds=rounds,
            vertices_before=len(original_proxy),vertices_after=len(proxy.data.vertices))
    before=coords(proxy).copy()
    group_fit=proxy.vertex_groups.new(name='StaticFit_BodyFacing_'+a.fit_inner_clump)
    fit_group_index=int(group_fit.index);fit_group_name=str(group_fit.name)
    weights=[]
    for vertex,pnt in zip(proxy.data.vertices,before):
        w=fit_weight(vertex,pnt);weights.append(w)
        if w>0:group_fit.add([vertex.index],w,'REPLACE')
    assert sum(w>.01 for w in weights)>10,'No body-facing clump surface selected'
    modifier=proxy.modifiers.new('Native_StaticInnerSurfaceFit','SHRINKWRAP')
    modifier.target=skinfit;modifier.wrap_method='NEAREST_SURFACEPOINT';modifier.wrap_mode='OUTSIDE_SURFACE'
    modifier.offset=a.inner_offset;modifier.vertex_group=fit_group_name
    bpy.ops.object.select_all(action='DESELECT');proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
    bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.context.view_layer.update()
    after=coords(proxy);assert len(after)==len(before)
    first_fit_displacement=float(np.linalg.norm(after-before,axis=1).max())
    cleanup_report=None
    if a.inner_cleanup_distance or a.inner_decimate_ratio:
        assert subdivision_report is not None,'Cleanup is only available with local subdivision'
        bm=bmesh.new();bm.from_mesh(proxy.data);bm.normal_update()
        layer=bm.verts.layers.deform.active
        def free_patch(v):
            point=proxy.matrix_world@v.co
            return (hard_tree.find(point)[2]>.02 and clump_tree.find(point)[2]<.018
                and skin_tree.find_nearest(point)[3]<.02)
        def patch_edges():
            return [e for e in bm.edges if all(free_patch(v) for v in e.verts)]
        edges=patch_edges();faces=list({f for e in edges for f in e.link_faces})
        vcount=len(bm.verts);fcount=len(bm.faces);selected_edge_count=len(edges)
        assert selected_edge_count>100,'Native cleanup patch selection was lost'
        if a.inner_decimate_ratio:
            assert 0<a.inner_decimate_ratio<1
            for face in bm.faces:face.select_set(False)
            for edge in bm.edges:edge.select_set(False)
            for vertex in bm.verts:vertex.select_set(False)
            selected_faces=[f for f in bm.faces if all(free_patch(v) for v in f.verts)]
            for face in selected_faces:face.select_set(True)
            selected_face_count=len(selected_faces)
            bm.to_mesh(proxy.data);bm.free();proxy.data.update()
            bpy.context.tool_settings.mesh_select_mode=(False,False,True)
            bpy.ops.object.mode_set(mode='EDIT')
            try:bpy.ops.mesh.decimate(ratio=a.inner_decimate_ratio,use_vertex_group=False,use_symmetry=False)
            finally:bpy.ops.object.mode_set(mode='OBJECT')
            bm=bmesh.new();bm.from_mesh(proxy.data)
            bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
        else:
            for _ in range(2):
                edges=patch_edges();faces=list({f for e in edges for f in e.link_faces})
                bmesh.ops.beautify_fill(bm,edges=edges,faces=faces,use_restrict_tag=False,method='AREA')
                bmesh.ops.dissolve_degenerate(bm,edges=patch_edges(),dist=a.inner_cleanup_distance)
                bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY')
        assert all(len(e.link_faces)==2 for e in bm.edges),'Native local cleanup produced nonmanifold edges'
        bm.normal_update();bm.to_mesh(proxy.data);bm.free();proxy.data.update()
        # Native conditional Outside wrap only restores the local skin envelope
        # after topology cleanup; it is applied once in the initial static asset.
        envelope=proxy.vertex_groups.new(name='StaticFit_PostCleanupSkinEnvelope')
        for vertex,pnt in zip(proxy.data.vertices,coords(proxy)):
            in_patch=any(g.group==fit_group_index and g.weight>.001 for g in vertex.groups)
            if in_patch and hard_tree.find(Vector(pnt))[2]>.02 and skin_tree.find_nearest(Vector(pnt))[3]<.0015:
                envelope.add([vertex.index],1.,'REPLACE')
        modifier=proxy.modifiers.new('Native_StaticPostCleanupEnvelope','SHRINKWRAP')
        modifier.target=skinfit;modifier.wrap_method='NEAREST_SURFACEPOINT';modifier.wrap_mode='OUTSIDE'
        modifier.offset=a.inner_offset;modifier.vertex_group=envelope.name
        bpy.ops.object.modifier_apply(modifier=modifier.name);bpy.context.view_layer.update()
        after=coords(proxy)
        cleanup_report=dict(method='Native beauty edge rotation, degenerate dissolve, triangulation and conditional Outside Shrinkwrap',
            dissolve_distance_m=a.inner_cleanup_distance,vertices_before=vcount,vertices_after=len(proxy.data.vertices),
            faces_before=fcount,faces_after=len(proxy.data.polygons),applied_to_free_patch_only=True,
            selected_edges=selected_edge_count,cleanup_passes=2,
            selection='Authored clump proximity <18mm, skin <20mm, hard root distance >20mm')
        if a.inner_decimate_ratio:
            cleanup_report.update(method='Native Edit Mode selected-face Decimate, beauty triangulation and conditional Outside Shrinkwrap',
                decimate_ratio=a.inner_decimate_ratio,selected_faces=selected_face_count,cleanup_passes=1)
    root_group=proxy.vertex_groups[settings['vertex_group_mass']]
    def root_weight(vertex):
        return next((g.weight for g in vertex.groups if g.group==root_group.index),0.)
    rebuilt_pins=np.array([root_weight(v)>.999 for v in proxy.data.vertices])
    assert rebuilt_pins.sum()==len(original_fixed_world),'Local subdivision changed fixed root count'
    root_tree=KDTree(int(rebuilt_pins.sum()))
    for i,pnt in enumerate(after[rebuilt_pins]):root_tree.insert(pnt,i)
    root_tree.balance()
    pin_change=max(root_tree.find(Vector(pnt))[2] for pnt in original_fixed_world)
    assert pin_change<1e-7,('Static fit changed the original fixed root patch',pin_change)
    fit_report=dict(method='Native static Shrinkwrap, nearest surface point, outside surface; simulation proxy only',
        clump=a.fit_inner_clump,offset_real_m=a.inner_offset,selected_vertices=sum(w>0 for w in weights),
        fully_selected_vertices=sum(w>.999 for w in weights),max_first_shrinkwrap_displacement_m=first_fit_displacement,
        original_fixed_root_coordinate_error_m=pin_change,
        selection='Body-facing normal, initial skin/clump proximity; 20-40mm authored hard-root protection fade; no frame-specific selection',
        display_vertices_modified=False,local_subdivision=subdivision_report,local_cleanup=cleanup_report)
    expected_proxy=after.copy()
    bpy.data.objects.remove(skinfit,do_unlink=True)
    bpy.ops.object.select_all(action='DESELECT');display.select_set(True);bpy.context.view_layer.objects.active=display
root=bpy.data.objects.new('Cloth_模拟坐标尺度',None);s.collection.objects.link(root);root.scale=(S,S,S)
physical_anchor=anchor.copy();physical_anchor.name='Cloth_放大空间头部附着';s.collection.objects.link(physical_anchor)
physical_anchor.parent=root;physical_anchor.matrix_parent_inverse=Matrix.Identity(4)
proxy.parent=physical_anchor;proxy.matrix_parent_inverse=Matrix.Identity(4);proxy.matrix_basis=Matrix.Identity(4)
body.matrix_world=Matrix.Scale(S,4)@body.matrix_world
s.gravity=s.gravity*S
cloth=proxy.modifiers.new('原生Cloth_全头代理物理','CLOTH')
cloth.show_viewport=False;cloth.show_render=False
for name,value in settings.items():setattr(cloth.settings,name,value)
for name,value in collision_settings.items():setattr(cloth.collision_settings,name,value)
for name,value in effector_settings.items():setattr(cloth.settings.effector_weights,name,value)
cloth.settings.quality=a.quality
if (fit_report and fit_report['local_subdivision']) or a.static_proxy_asset:
    cloth.settings.mass=config['moving_mass_kg']/(len(proxy.data.vertices)-int(rebuilt_pins.sum()))
drag_profile=None
if a.normalise_air_damping:
    before=cloth.settings.air_damping;reference_vertex_mass=.005
    cloth.settings.air_damping=before*cloth.settings.mass/reference_vertex_mass
    drag_profile=dict(reference_vertex_mass_kg=reference_vertex_mass,before=before,
        after=cloth.settings.air_damping,reason='Preserve native velocity-drag/mass ratio against the 5g vertex reference when normalizing proxy mass; not a claim of measured real hair drag')
# Blender divides linear stiffness by mean spring length and multiplies its
# angular coefficient by rest edge length. Scale the material coefficients
# with simulation length; velocity drag/damping and vertex masses stay fixed.
material_fields=['tension_stiffness','tension_stiffness_max','compression_stiffness','compression_stiffness_max',
    'shear_stiffness','shear_stiffness_max','bending_stiffness','bending_stiffness_max',
    'internal_tension_stiffness','internal_tension_stiffness_max','internal_compression_stiffness','internal_compression_stiffness_max']
changed={}
for name in material_fields:
    before=getattr(cloth.settings,name);setattr(cloth.settings,name,before*S)
    changed[name]=dict(before=before,after=getattr(cloth.settings,name))
cloth.settings.internal_spring_max_length=settings['internal_spring_max_length']*S
cloth.collision_settings.distance_min=collision_settings['distance_min']*S
if a.body_margin_real is not None:cloth.collision_settings.distance_min=a.body_margin_real*S*.5
# Keep the native API's minimum epsilon in solver units: 0.1mm per side in
# display metres for scale 10. All self/body collisions remain enabled.
cloth.collision_settings.self_distance_min=collision_settings['self_distance_min']
target=bpy.data.objects.new('HairProxy_原生本地坐标回传',bpy.data.meshes.new('NativeLocalSpaceRelay'))
s.collection.objects.link(target);target.parent=anchor;target.matrix_parent_inverse=Matrix.Identity(4);target.matrix_basis=Matrix.Identity(4)
group=bpy.data.node_groups.new('Native_ClothLocalSpaceRelay','GeometryNodeTree')
group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
info=group.nodes.new('GeometryNodeObjectInfo');info.transform_space='ORIGINAL';info.inputs['Object'].default_value=proxy
output=group.nodes.new('NodeGroupOutput');group.links.new(info.outputs['Geometry'],output.inputs['Geometry'])
md=target.modifiers.new('原生GeometryNodes_模拟本地空间','NODES');md.node_group=group;target.hide_render=True;target.display_type='WIRE'
bpy.context.view_layer.update()
relay_error=float(np.max(np.abs(coords(target)-expected_proxy)))
assert relay_error<5e-6,('Native local-space relay transform mismatch',relay_error)
deform.target=target;bpy.context.view_layer.objects.active=display
bpy.ops.object.surfacedeform_bind(modifier=deform.name);assert deform.is_bound
initial_error=float(np.max(np.abs(coords(display)-expected_display)))
assert initial_error<5e-6,('Binding changed complete initial hair',initial_error)
exp=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware'
expected_body=np.load(exp/'body.npy',mmap_mode='r');errors=[];head_errors=[]
for frame in range(1,s.frame_end+1):
    s.frame_set(frame);bpy.context.view_layer.update()
    errors.append(float(np.max(np.abs(coords(body)/S-expected_body[(frame-1)*8]))))
    original=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)
    normalized=np.array(physical_anchor.matrix_world);normalized[:3,:]/=S
    head_errors.append(float(np.max(np.abs(normalized-original))))
assert max(errors)<5e-6,('Physical collider time/scale mismatch',max(errors))
assert max(head_errors)<5e-6,('Physical attachment time/scale mismatch',max(head_errors))
s.frame_set(1);bpy.context.view_layer.update()
body.modifiers.new('原生Cloth_放大空间皮肤碰撞','COLLISION')
for name,value in body_settings.items():setattr(body.collision,name,value)
body.collision.thickness_outer=body_settings['thickness_outer']*S
body.collision.thickness_inner=body_settings['thickness_inner']*S
if a.body_margin_real is not None:
    body.collision.thickness_outer=a.body_margin_real*S*.5
    body.collision.thickness_inner=a.body_margin_real*S*.5
pc=cloth.point_cache;pc.frame_start=1;pc.frame_end=s.frame_end;pc.use_disk_cache=True
cloth.show_viewport=True;cloth.show_render=True;proxy.hide_render=True
bpy.context.view_layer.update()
assert np.max(np.abs(coords(target)-coords(proxy)/S))<5e-6
assert np.max(np.abs(coords(display)-expected_display))<5e-6
bpy.ops.wm.save_as_mainfile(filepath=str(path))
for name in ['clump_proxy_rest.npz','clump_assets.json','geometric_topology.json']:
    shutil.copy2(baseline/name,out/name)
if a.static_proxy_asset:
    shutil.copy2(a.static_proxy_asset,out/'clump_proxy_rest.npz')
    shutil.copy2(Path(a.static_proxy_asset).parent/'geometric_topology.json',out/'geometric_topology.json')
    shutil.copy2(Path(a.static_proxy_asset).parent/'remesh_report.json',out/'remesh_report.json')
if fit_report is not None:
    old=np.load(baseline/'clump_proxy_rest.npz');arrays={k:old[k] for k in old.files}
    arrays['vertices']=np.array([v.co[:] for v in proxy.data.vertices])
    if fit_report['local_subdivision']:
        proxy.data.calc_loop_triangles()
        arrays['triangles']=np.array([t.vertices[:] for t in proxy.data.loop_triangles],np.int32)
        arrays['pins']=rebuilt_pins
        old_tree=KDTree(len(old['vertices']))
        for i,pnt in enumerate(old['vertices']):old_tree.insert(pnt,i)
        old_tree.balance()
        closest=np.array([old_tree.find(Vector(pnt))[1] for pnt in arrays['vertices']])
        arrays['clump_ids']=old['clump_ids'][closest]
        adjacency=[[] for _ in proxy.data.vertices]
        for e in proxy.data.edges:
            i,j=e.vertices;adjacency[i].append(j);adjacency[j].append(i)
        component_ids=np.full(len(adjacency),-1,np.int64);components=[]
        for start in range(len(adjacency)):
            if component_ids[start]>=0:continue
            ci=len(components);stack=[start];members=[];component_ids[start]=ci
            while stack:
                i=stack.pop();members.append(i)
                for j in adjacency[i]:
                    if component_ids[j]<0:component_ids[j]=ci;stack.append(j)
            components.append(dict(vertices=len(members),rooted=bool(rebuilt_pins[members].any())))
        assert len(components)==1 and components[0]['rooted'],'Local subdivision split the original connected proxy'
        arrays['component_ids']=component_ids
        topology=dict(raw_vertices=len(old['vertices']),vertices=len(adjacency),triangles=len(arrays['triangles']),
            components=components,pins=int(rebuilt_pins.sum()),deleted_components=0,all_27_groups_tracked=True,
            physical_clump_splits=False,manifold_clean_asset=True,post_import_simplification=False,
            native_local_subdivision=fit_report['local_subdivision'])
        (out/'geometric_topology.json').write_text(json.dumps(topology,ensure_ascii=False,indent=2),'utf8')
    np.savez_compressed(out/'clump_proxy_rest.npz',**arrays)
    (out/'inner_fit.json').write_text(json.dumps(fit_report,ensure_ascii=False,indent=2),'utf8')
config.update(blend=str(path),simulation_scale=S,physics_binding_target=target.name,cloth_quality=cloth.settings.quality,
    proxy_vertices=len(proxy.data.vertices),proxy_polygons=len(proxy.data.polygons),
    actual_mass_per_vertex_kg=cloth.settings.mass,mass_per_vertex_kg=cloth.settings.mass,
    self_collision_distance_world_units=cloth.collision_settings.self_distance_min,
    self_collision_distance_m=cloth.collision_settings.self_distance_min/S,
    cloth_collision_distance_world_units=cloth.collision_settings.distance_min,
    cloth_collision_distance_m=cloth.collision_settings.distance_min/S,
    body_collision_outer_world_units=body.collision.thickness_outer,
    body_collision_outer_m=body.collision.thickness_outer/S,
    original_geometry_modified=False,initial_native_relay_error_m=relay_error,initial_display_error_m=initial_error,
    normalized_physics_body_error_m=max(errors),normalized_physics_head_matrix_error=max(head_errors),
    physics_baked=False,acceptance='NOT_ACCEPTED',scaled_material_parameters=changed,
    gravity_world_units=list(s.gravity),scale_profile_source=str(baseline),
    mass_normalized_air_damping=drag_profile,
    static_inner_fit=fit_report,
    static_proxy_asset=str(a.static_proxy_asset) if a.static_proxy_asset else None,
    static_proxy_asset_report=static_asset_report,
    native_self_epsilon_api_hard_min=cloth.collision_settings.bl_rna.properties['self_distance_min'].hard_min)
(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(status='SCALED_NATIVE_CANDIDATE_READY',blend=str(path),simulation_scale=S,
    initial_display_error_m=initial_error,initial_relay_error_m=relay_error,
    self_pair_real_distance_m=2*config['self_collision_distance_m']),ensure_ascii=False),flush=True)
