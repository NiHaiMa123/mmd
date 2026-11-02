"""Prepare a separate stock Blender Cloth cage and stock Surface Deform binding.

All physical integration, collision response and display binding are Blender's.
This adapter prepares the asset, pins and independent attachment animation only.
"""
import argparse,json,sys,time,traceback,struct,shutil
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=360);p.add_argument('--bake',action='store_true');p.add_argument('--clumps',action='store_true')
p.add_argument('--regular-ribbons',action='store_true');p.add_argument('--moving-mass',type=float,default=.12)
p.add_argument('--geometric-volume',help='Static unsigned union asset directory')
p.add_argument('--cloth-quality',type=int,default=32)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'status.json').exists(),'Choose a fresh output directory'
base=ROOT.parent/'work/headswap_xl_codex';started=time.monotonic()
def status(stage,**kw):
    d=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);q=out/'status.tmp.json';q.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');q.replace(out/'status.json');print('STANDARD_PROXY',json.dumps(d,ensure_ascii=False),flush=True)
def active(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.hide_set(False);obj.select_set(True);bpy.context.view_layer.objects.active=obj
def tree_of(points):
    t=KDTree(len(points))
    for i,v in enumerate(points):t.insert(v,i)
    t.balance();return t
try:
    status('OPENING_COMPLETE_SCENE')
    engine('import_export').ensure_mmd_tools();source=base/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend'
    bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False,load_ui=False)
    s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.render.fps=30;s.use_preview_range=False
    if s.rigidbody_world:s.rigidbody_world.enabled=False
    actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架']
    z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];hard=z['same_true_hard_root_mask']
    if actor.data.attributes.get('SourceVertexID') is None:
        attr=actor.data.attributes.new('SourceVertexID','INT','POINT');attr.data.foreach_set('value',np.arange(len(actor.data.vertices),dtype=np.int32))
    s.frame_set(1);bpy.context.view_layer.update();expected=coords(actor)[ids];head0=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);inv0=np.linalg.inv(head0)
    expected_local=expected@inv0[:3,:3].T+inv0[:3,3]
    # Render geometry retains evaluated UV/material/normal/surface-ID data.
    # Original body object, all 232 keys and all original actions stay intact.
    ev=actor.evaluated_get(bpy.context.evaluated_depsgraph_get());data=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get())
    bm=bmesh.new();bm.from_mesh(data);layer=bm.verts.layers.int['SourceVertexID'];keep=set(map(int,ids));bmesh.ops.delete(bm,geom=[v for v in bm.verts if int(v[layer]) not in keep],context='VERTS');bm.to_mesh(data);bm.free()
    display=bpy.data.objects.new('完整头发_标准代理绑定',data);s.collection.objects.link(display)
    original=np.array([v.value for v in data.attributes['SourceVertexID'].data]);lookup={int(v):i for i,v in enumerate(original)}
    assert set(original)==set(ids)
    normal_transform=(Matrix(inv0)@actor.matrix_world).inverted().transposed().to_3x3()
    free_normals=data.attributes.get('custom_normal');normal_values=None;corner_normals=None
    if free_normals is not None and free_normals.data_type=='FLOAT_VECTOR':
        normal_values=np.empty(len(free_normals.data)*3,np.float32);free_normals.data.foreach_get('vector',normal_values);normal_values=normal_values.reshape(-1,3)@np.array(normal_transform).T
    elif data.has_custom_normals:corner_normals=[normal_transform@n.vector for n in data.corner_normals]
    data.vertices.foreach_set('co',np.asarray([expected_local[lookup0] for lookup0 in [int(np.searchsorted(ids,i)) for i in original]],np.float32).ravel())
    if normal_values is not None:free_normals.data.foreach_set('vector',normal_values.astype(np.float32).ravel())
    elif corner_normals is not None:data.normals_split_custom_set(corner_normals)
    data.update()
    # A separate native attachment object prevents a rig/cloth dependency cycle.
    anchor=bpy.data.objects.new('HairProxy_独立头部附着',None);s.collection.objects.link(anchor);anchor.rotation_mode='QUATERNION'
    samples=[]
    status('BAKING_INDEPENDENT_HEAD_ATTACHMENT')
    for f in np.arange(1,a.last+.001,.25):
        s.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();samples.append((float(f),(arm.matrix_world@arm.pose.bones['頭'].matrix).copy()))
    for f,matrix in samples:
        anchor.matrix_world=matrix
        for prop in ('location','rotation_quaternion','scale'):anchor.keyframe_insert(data_path=prop,frame=f)
    anchor.animation_data.action.name='HairProxy_头部世界动作_独立采样'
    s.frame_set(1);bpy.context.view_layer.update();display.parent=anchor;display.matrix_parent_inverse=Matrix.Identity(4);display.matrix_basis=Matrix.Identity(4)
    # A finite-volume low-resolution cage, made by stock Solidify/Remesh/
    # Decimate. These modifiers operate on the simulation copy only.
    clump_reports=[];targets=[];removed=0
    if a.geometric_volume:
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from geometric_hair_proxy_asset import construct
        status('BUILDING_SHARED_GEOMETRIC_CAGE')
        proxy,pins,clump_reports,targets,labels,components=construct(base,s,anchor,expected_local,ids,hard,Path(a.geometric_volume),out)
        (out/'clump_assets.json').write_text(json.dumps(clump_reports,ensure_ascii=False,indent=2),'utf8')
    elif a.clumps:
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from standard_clump_proxy_asset import construct
        status('BUILDING_ALL_27_CONTINUOUS_CLUMP_CAGES')
        proxy,pins,clump_reports,targets,labels=construct(base,s,anchor,expected_local,ids,hard,checkpoint=out,regular_open=a.regular_ribbons)
        components=[dict(vertices=r['vertices'],rooted=r['pins']>0) for r in clump_reports]
        (out/'clump_assets.json').write_text(json.dumps(clump_reports,ensure_ascii=False,indent=2),'utf8')
    else:
        proxydata=data.copy();proxy=bpy.data.objects.new('HairProxy_全头体积模拟网格',proxydata);s.collection.objects.link(proxy);proxy.parent=anchor;proxy.matrix_parent_inverse=Matrix.Identity(4);proxy.matrix_basis=Matrix.Identity(4)
        active(proxy);status('BUILDING_NATIVE_SIMULATION_CAGE')
        solid=proxy.modifiers.new('代理厚度_仅模拟','SOLIDIFY');solid.thickness=.006;solid.offset=0.;solid.use_even_offset=True;bpy.ops.object.modifier_apply(modifier=solid.name)
        remesh=proxy.modifiers.new('代理体素重拓扑','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.003;remesh.use_smooth_shade=True;bpy.ops.object.modifier_apply(modifier=remesh.name)
        before=len(proxy.data.vertices)
        if before>6000:
            dec=proxy.modifiers.new('代理简化_仅模拟','DECIMATE');dec.ratio=6000/before;dec.use_collapse_triangulate=True;bpy.ops.object.modifier_apply(modifier=dec.name)
        alltree=tree_of(expected_local);fixed_by_source={int(i):bool(h) for i,h in zip(ids,hard)}
        pins=np.array([fixed_by_source[int(ids[alltree.find(v.co)[1]])] for v in proxy.data.vertices])
        bm=bmesh.new();bm.from_mesh(proxy.data);bm.verts.ensure_lookup_table();seen=set();drop=[];components=[]
        for seed in bm.verts:
            if seed.index in seen:continue
            stack=[seed];component=[];seen.add(seed.index)
            while stack:
                v=stack.pop();component.append(v)
                for edge in v.link_edges:
                    other=edge.other_vert(v)
                    if other.index not in seen:seen.add(other.index);stack.append(other)
            rooted=any(pins[v.index] for v in component);components.append(dict(vertices=len(component),rooted=rooted))
            if not rooted:drop.extend(component)
        removed=len(drop)
        if drop:bmesh.ops.delete(bm,geom=drop,context='VERTS')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(proxy.data);bm.free()
        assert len(proxy.data.vertices)>100,'Proxy vanished during remeshing'
        pins=np.array([fixed_by_source[int(ids[alltree.find(v.co)[1]])] for v in proxy.data.vertices])
    pin=proxy.vertex_groups.new(name='真实头部固定区');pin.add(np.flatnonzero(pins).tolist(),1.,'REPLACE');assert pins.sum()>0
    # Proxy construction and binding distances are diagnostics, not a physical
    # guarantee. Every original render vertex remains in the display object.
    proxy_tree=tree_of([v.co for v in proxy.data.vertices]);dist=np.array([proxy_tree.find(v)[2] for v in expected_local])
    report=dict(source=str(source),method='Stock Blender Solidify + Voxel Remesh + Decimate, Cloth, Surface Deform',source_keys=len(actor.data.shape_keys.key_blocks),hair_vertices=len(ids),render_hair_triangles=40181,source_hard_roots=int(hard.sum()),proxy_vertices=len(proxy.data.vertices),proxy_polygons=len(proxy.data.polygons),proxy_pins=int(pins.sum()),removed_unattached_proxy_vertices=removed,proxy_components_before_filter=components,display_to_proxy_vertex_distance_p95_m=float(np.quantile(dist,.95)),display_to_proxy_vertex_distance_max_m=float(dist.max()),self_collision=True,physics_baked=False,frames=[1,a.last],acceptance='NOT_ACCEPTED')
    if a.clumps:
        report.update(method='Per-clump structured ribbon cage asset; native static Shrinkwrap fit, Solidify, Cloth and per-clump Surface Deform',clumps=clump_reports,maximum_dynamic_clump_surface_distance_m=max(r['nearest_surface_max_m'] for r in clump_reports),clumps_with_coverage_failure=[r['name'] for r in clump_reports if r['nearest_surface_p95_m']>.006 or r['nearest_surface_max_m']>.015],root_attachment_review_failures=[r['name'] for r in clump_reports if r['root_pin_max_distance_to_authored_root_set_m']>.015])
    if a.regular_ribbons:report.update(method='Regular single-layer finite-width ribbons; no projection or Solidify; native Cloth and per-clump Surface Deform',regular_open_ribbons=True,moving_mass_kg=a.moving_mass,mass_per_vertex_kg=a.moving_mass/(len(proxy.data.vertices)-int(pins.sum())),initial_contact_audit_required=True)
    if a.geometric_volume:
        volume_report=json.loads((Path(a.geometric_volume)/'volume_asset.json').read_text('utf8'))
        volume_clean=bool(volume_report.get('manifold_cleanup'))
        report.update(method='Shared geometric unsigned voxel union; stock Cloth and Surface Deform',geometric_volume=True,
            asset=str(a.geometric_volume),clumps=clump_reports,initial_contact_audit_required=True,
            moving_mass_kg=a.moving_mass,mass_per_vertex_kg=a.moving_mass/(len(proxy.data.vertices)-int(pins.sum())),
            clumps_with_coverage_failure=[r['name'] for r in clump_reports if r['nearest_surface_p95_m']>.006 or r['nearest_surface_max_m']>.015],
            root_attachment_review_failures=[r['name'] for r in clump_reports if r['root_pin_max_distance_to_authored_root_set_m']>.015])
        if volume_clean:
            report.update(manifold_clean_asset=True,coverage_gate='All 27 groups: inside volume or outside within 8mm; original surface distances retained as diagnostics',
                clumps_with_coverage_failure=[r['name'] for r in clump_reports if not r['coverage_pass']])
    (out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    status('BINDING_STOCK_SURFACE_DEFORM',proxy_vertices=len(proxy.data.vertices))
    cloth=proxy.modifiers.new('原生Cloth_全头代理物理','CLOTH');settings=cloth.settings
    settings.quality=a.cloth_quality;settings.mass=.005;settings.air_damping=5.;settings.vertex_group_mass=pin.name;settings.pin_stiffness=1.
    if a.regular_ribbons or a.geometric_volume:settings.mass=report['mass_per_vertex_kg'];settings.air_damping=1.
    settings.tension_stiffness=1000;settings.compression_stiffness=1000;settings.shear_stiffness=1000;settings.bending_stiffness=20
    if a.regular_ribbons or a.geometric_volume:settings.bending_stiffness=.1
    settings.use_internal_springs=bool(a.geometric_volume) or not a.clumps;settings.internal_spring_max_length=.03;settings.internal_spring_max_diversion=.785398
    settings.internal_tension_stiffness=100;settings.internal_compression_stiffness=100
    cloth.collision_settings.use_self_collision=True;cloth.collision_settings.self_distance_min=.0005 if a.clumps else .0015;cloth.collision_settings.collision_quality=16;cloth.collision_settings.distance_min=.003
    cloth.show_viewport=False;cloth.show_render=False
    if a.clumps and not a.geometric_volume:
        for ci,target in enumerate(targets):
            movable=display.vertex_groups.new(name='ClumpBinding_'+str(ci));movable.add([lookup[int(i)] for i in ids[(labels==ci)&~hard]],1.,'REPLACE')
            deform=display.modifiers.new('SurfaceDeform_发束_'+str(ci),'SURFACE_DEFORM');deform.target=target;deform.vertex_group=movable.name;deform.use_sparse_bind=True
            active(display);bpy.ops.object.surfacedeform_bind(modifier=deform.name);assert deform.is_bound,('Clump binding failed',ci)
    else:
        movable=display.vertex_groups.new(name='原始动态发区_不移动真实硬根');movable.add([lookup[int(i)] for i in ids[~hard]],1.,'REPLACE')
        if a.geometric_volume and volume_clean:
            authored=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
            dynamic_weights=np.clip(authored['chain_weights'].sum(axis=1),0.,1.)
            assert np.array_equal(authored['ids'],ids)
            for i,w in zip(ids[~hard],dynamic_weights[~hard]):movable.add([lookup[int(i)]],float(w),'REPLACE')
            report['binding_influence']='Original summed hair-bone weights; authored head/hair transition retained, hard roots excluded'
            report['dynamic_binding_weight_range']=[float(dynamic_weights[~hard].min()),float(dynamic_weights[~hard].max())]
        deform=display.modifiers.new('标准SurfaceDeform_完整渲染发片','SURFACE_DEFORM');deform.target=proxy;deform.vertex_group=movable.name;deform.use_sparse_bind=True
        active(display);bpy.ops.object.surfacedeform_bind(modifier=deform.name);assert deform.is_bound,'Surface Deform did not bind'
    s.frame_set(1);bpy.context.view_layer.update();actual=coords(display);mapped=np.array([actual[lookup[int(i)]] for i in ids]);initial_error=float(np.max(np.abs(mapped-expected)))
    report['initial_display_error_m']=initial_error;assert initial_error<2e-5,('Binding changed original groom',initial_error)
    mask=actor.vertex_groups.new(name='StandardProxy_完整头发独立显示');mask.add(ids.tolist(),1.,'REPLACE');md=actor.modifiers.new('完整头发由标准代理驱动','MASK');md.vertex_group=mask.name;md.invert_vertex_group=True
    s['HairDisplayObject']=display.name
    # Real deformed skin triangles only: no artificial closure caps stretched
    # across empty space. Existing body/wrist corrections remain the source.
    body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];export=base/'fullhair_repro_20261030/input_body_aware'
    flags=np.load(export/'real_body_faces.npy').astype(bool);bodyfaces=np.load(export/'body_faces.npy')[flags];bodyverts=np.array([v.co[:] for v in body.data.vertices]);body.data.clear_geometry();body.data.from_pydata(bodyverts.tolist(),[],bodyfaces.tolist());body.data.update()
    cachemod=next(md for md in body.modifiers if md.type=='MESH_CACHE')
    with Path(bpy.path.abspath(cachemod.filepath)).open('rb') as stream:magic,version,count,first,step,samples_count=struct.unpack('<12siiffi',stream.read(32))
    assert magic==b'POINTCACHE2\0' and count==len(body.data.vertices)
    cachemod.play_mode='CUSTOM';cachemod.time_mode='FRAME';cachemod.driver_add('eval_frame').driver.expression=f'(frame - {first:.17g}) / {step:.17g}'
    body.modifiers.new('标准Cloth_实际皮肤碰撞','COLLISION');body.collision.thickness_outer=.003;body.collision.thickness_inner=.001;body.collision.use_culling=False
    if a.regular_ribbons or a.geometric_volume:body.collision.thickness_outer=.001;cloth.collision_settings.distance_min=.001
    report.update(cloth_collision_distance_m=cloth.collision_settings.distance_min,body_collision_outer_m=body.collision.thickness_outer,self_collision_distance_m=cloth.collision_settings.self_distance_min,actual_mass_per_vertex_kg=settings.mass,bending_stiffness=settings.bending_stiffness,cloth_quality=settings.quality,collision_quality=cloth.collision_settings.collision_quality)
    collection=bpy.data.collections.new('HairProxy_实际皮肤碰撞');s.collection.children.link(collection);collection.objects.link(body);cloth.collision_settings.collection=collection
    expected_body=np.load(export/'body.npy',mmap_mode='r');bodyerrors=[];headerrors=[]
    status('CHECKING_SOURCE_TIME_AND_ATTACHMENT')
    for frame in range(1,a.last+1):
        s.frame_set(frame);bpy.context.view_layer.update();bodyerrors.append(float(np.max(np.abs(coords(body)-expected_body[(frame-1)*8]))));headerrors.append(float(np.max(np.abs(np.array(anchor.matrix_world)-np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)))))
    report['max_body_replay_error_m']=max(bodyerrors);report['max_head_matrix_error']=max(headerrors)
    assert max(bodyerrors)<5e-6,('Body cache not synchronized',max(bodyerrors));assert max(headerrors)<5e-6,('Independent head attachment mismatch',max(headerrors))
    cache=out/'cache';cache.mkdir(exist_ok=True)
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type=='MESH_CACHE':
                old=Path(bpy.path.abspath(md.filepath));target=cache/old.name
                if not target.exists():shutil.copy2(old,target)
                md.filepath=str(target)
    proxy.hide_render=True;proxy.display_type='WIRE';pc=cloth.point_cache;pc.frame_start=1;pc.frame_end=a.last;pc.use_disk_cache=True
    s.frame_set(1);bpy.context.view_layer.update();cloth.show_viewport=True;cloth.show_render=True
    path=out/'完整角色_标准模拟代理_11秒待验收.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
    report['blend']=str(path);(out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    if a.bake:
        if a.regular_ribbons or a.geometric_volume:
            audit=json.loads((out/'rest_audit/initial_contact_analysis.json').read_text('utf8'))
            assert audit['self_audit_complete'] and audit['same_clump_crossing_pairs']==0 and audit['between_clump_crossing_pairs']==0 and audit['proxy_body_crossing_pairs']==0 and audit['free_vertices_inside_configured_body_margin']==0,'Static rest contact audit must pass before any dynamics'
        if a.clumps:
            assert not report['clumps_with_coverage_failure'],('STOP: clump surface coverage failed',report['clumps_with_coverage_failure'])
            assert not report['root_attachment_review_failures'],('STOP: clump root attachment review failed',report['root_attachment_review_failures'])
        else:assert report['display_to_proxy_vertex_distance_max_m']<.025, 'STOP: simulation cage does not cover the complete render hair; do not bake'
        assert len([c for c in components if c['rooted']])<=len(json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))['chains'])+1, 'STOP: fragmented simulation cage requires topology review'
        def progress(scene,*_):
            if scene.frame_current%15==0:status('BAKING_STOCK_CLOTH',frame=scene.frame_current,last=a.last)
        bpy.app.handlers.frame_change_pre.append(progress);active(proxy);status('BAKING_STOCK_CLOTH',frame=1,last=a.last)
        with bpy.context.temp_override(scene=s,object=proxy,active_object=proxy,point_cache=pc):bpy.ops.ptcache.bake(bake=True)
        bpy.app.handlers.frame_change_pre.remove(progress);assert pc.is_baked
        s.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(path));report['physics_baked']=True
        (out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    status('BAKED_REQUIRES_REOPEN_AND_FULL_HEAD_REVIEW' if a.bake else 'CONFIGURED_REQUIRES_REVIEW',**report)
except BaseException as exc:
    status('STOPPED_ON_PROBLEM',error=repr(exc),traceback=traceback.format_exc());raise
