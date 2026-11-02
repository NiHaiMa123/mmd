"""Use stock Blender Cloth on the actual hair mesh, with native pin/collision.

No dynamics, contact projection or temporal smoothing is implemented here.
The script only prepares the existing mesh and invokes Blender's cache bake.
"""
import argparse,json,shutil,struct,sys,time,traceback
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=450)
p.add_argument('--seam-tolerance',type=float,default=0.);p.add_argument('--preroll',type=int,default=0)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
base=ROOT.parent/'work/headswap_xl_codex';source=base/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend';start=time.monotonic()
def status(stage,**kw):
    data=dict(stage=stage,elapsed_s=time.monotonic()-start,**kw);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('NATIVE_MESH_CLOTH',json.dumps(data,ensure_ascii=False),flush=True)
try:
    status('PREPARING_ACTUAL_HAIR_MESH')
    engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False,load_ui=False)
    s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.render.fps=30;s.use_preview_range=False
    m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架']
    z=np.load(base/'hair_initial_repair_20261030/DELIVER_INITIAL/InitialHairRest.npz');ids=z['ids'];hard=z['same_true_hard_root_mask']
    s.frame_set(1);bpy.context.view_layer.update();expected=coords(m)[ids]
    attr=m.data.attributes.new('SourceVertexID','INT','POINT');attr.data.foreach_set('value',np.arange(len(m.data.vertices),dtype=np.int32))
    hair=m.copy();hair.data=m.data.copy();hair.name='完整头发_原生Cloth_实际发片';s.collection.objects.link(hair)
    for mod in list(hair.modifiers):
        if mod.type!='ARMATURE':hair.modifiers.remove(mod)
    # Edit-mode deletion preserves native UVs, weights, normals and shape keys.
    hair.hide_set(False);hair.hide_viewport=False;hair.hide_render=False
    bpy.ops.object.select_all(action='DESELECT');hair.select_set(True);bpy.context.view_layer.objects.active=hair
    s.tool_settings.mesh_select_mode=(True,False,False)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.reveal(select=False);bpy.ops.mesh.select_all(action='DESELECT')
    bm=bmesh.from_edit_mesh(hair.data);layer=bm.verts.layers.int['SourceVertexID'];keep=set(map(int,ids))
    for vertex in bm.verts:vertex.select_set(int(vertex[layer]) not in keep)
    bmesh.update_edit_mesh(hair.data);bpy.ops.mesh.delete(type='VERT');bpy.ops.object.mode_set(mode='OBJECT')
    original=np.array([x.value for x in hair.data.attributes['SourceVertexID'].data]);lookup={int(v):i for i,v in enumerate(original)}
    assert set(original)==set(ids),(len(original),len(ids),len(set(original)-set(ids)),len(set(ids)-set(original)))
    seams=[];component_report={}
    if a.seam_tolerance>0:
        # Standard native sewing springs connect split render/UV seams. Match
        # original rest geometry, not the temporarily separated groomed seam.
        basis=np.array([v.co[:] for v in hair.data.shape_keys.key_blocks[0].data]);n=len(basis);parent=np.arange(n)
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
            return i
        for e in hair.data.edges:parent[find(e.vertices[0])]=find(e.vertices[1])
        raw=np.array([find(i) for i in range(n)])
        tree=KDTree(n)
        for i,co in enumerate(basis):tree.insert(co,i)
        tree.balance()
        for i,co in enumerate(basis):
            for _,j,distance in tree.find_range(co,a.seam_tolerance):
                if j>i and raw[i]!=raw[j]:seams.append((i,j))
        bpy.ops.object.mode_set(mode='EDIT');bm=bmesh.from_edit_mesh(hair.data);layer=bm.verts.layers.int['SourceVertexID']
        bysource={int(v[layer]):v for v in bm.verts}
        for i,j in seams:
            pair=(bysource[int(original[i])],bysource[int(original[j])])
            if bm.edges.get(pair) is None:bm.edges.new(pair)
        bmesh.update_edit_mesh(hair.data);bpy.ops.object.mode_set(mode='OBJECT')
        for i,j in seams:parent[find(i)]=find(j)
        rooted={find(lookup[int(i)]) for i in ids[hard]};components={find(i) for i in range(n)}
        component_report=dict(raw_components=len(set(raw)),stitched_components=len(components),unanchored_components=len(components-rooted),added_sewing_edges=len(seams),tolerance_m=a.seam_tolerance)
        assert not components-rooted,('Unattached physical hair pieces remain',component_report)
        (out/'seam_attachment.json').write_text(json.dumps(component_report,indent=2),'utf8');np.save(out/'native_sewing_edges.npy',np.array(seams,np.int32))
    if a.preroll:
        # Hold only the existing attachment bones during negative-frame
        # preroll. Constraints are exactly inactive on every delivered frame.
        # The original input weights, shape keys and Actions remain unchanged.
        for name in ['首','頭']:
            bone=arm.pose.bones[name];anchor=bpy.data.objects.new('Cloth_预热首帧_'+name,None);s.collection.objects.link(anchor);anchor.matrix_world=arm.matrix_world@bone.matrix;anchor.hide_render=True
            constraint=bone.constraints.new('COPY_TRANSFORMS');constraint.name='仅负帧预热_正片完全停用';constraint.target=anchor;constraint.owner_space='WORLD';constraint.target_space='WORLD'
            constraint.driver_add('influence').driver.expression='1 if frame < 1 else 0'
    pin=hair.vertex_groups.new(name='Cloth_真实发根固定');pin.add([lookup[int(v)] for v in ids[hard]],1.,'REPLACE')
    mask=m.vertex_groups.new(name='Cloth_分离显示的全部头发');mask.add(ids.tolist(),1.,'REPLACE')
    mod=m.modifiers.new('完整头发由独立原生Cloth对象显示','MASK');mod.vertex_group=mask.name;mod.invert_vertex_group=True
    body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];body.modifiers.new('Native_Hair_Collision','COLLISION')
    # Mesh Cache FRAME playback counts samples; it does not apply the PC2
    # sample interval automatically. Use the documented custom frame driver.
    body_cache=next(md for md in body.modifiers if md.type=='MESH_CACHE')
    with Path(bpy.path.abspath(body_cache.filepath)).open('rb') as stream:
        magic,version,count,first,step,samples=struct.unpack('<12siiffi',stream.read(32))
    assert magic==b'POINTCACHE2\0' and count==len(body.data.vertices)
    body_cache.play_mode='CUSTOM';body_cache.time_mode='FRAME'
    body_cache.driver_add('eval_frame').driver.expression=f'(frame - {first:.17g}) / {step:.17g}'
    body.collision.thickness_outer=.003;body.collision.thickness_inner=.001;body.collision.use_culling=False
    collection=bpy.data.collections.new('NativeHair_身体碰撞');s.collection.children.link(collection);collection.objects.link(body)
    cloth=hair.modifiers.new('原生Cloth_完整真实发片','CLOTH');settings=cloth.settings
    settings.quality=20;settings.mass=.005;settings.air_damping=10;settings.vertex_group_mass=pin.name;settings.pin_stiffness=1
    settings.tension_stiffness=1000;settings.compression_stiffness=1000;settings.shear_stiffness=1000;settings.bending_stiffness=50
    if seams:settings.use_sewing_springs=True;settings.sewing_force_max=10.
    cloth.collision_settings.collection=collection;cloth.collision_settings.use_collision=True;cloth.collision_settings.use_self_collision=False
    cloth.collision_settings.distance_min=.003;cloth.collision_settings.collision_quality=12
    cache=out/'cache';cache.mkdir(exist_ok=True)
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type=='MESH_CACHE':
                old=Path(bpy.path.abspath(md.filepath));new=cache/old.name
                if not new.exists():shutil.copy2(old,new)
                md.filepath=str(new)
    pc=cloth.point_cache;pc.frame_start=1-a.preroll;pc.frame_end=a.last;pc.use_disk_cache=True
    # Validate the actual physical collider before spending time on simulation.
    cloth.show_viewport=False;cloth.show_render=False
    expected_body=np.load(base/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r')
    errors=[]
    for frame in range(1,a.last+1):
        s.frame_set(frame);bpy.context.view_layer.update();errors.append(float(np.abs(coords(body)-expected_body[(frame-1)*8]).max()))
    replay=dict(frames=a.last,max_error_m=max(errors),source_step=step,driver=body_cache.animation_data if hasattr(body_cache,'animation_data') else body_cache.path_from_id('eval_frame'))
    (out/'body_cache_replay.json').write_text(json.dumps(replay,default=str,indent=2),'utf8')
    assert max(errors)<5e-6,('Physical collider is out of time',max(errors))
    s.frame_set(1);bpy.context.view_layer.update()
    hc=coords(hair);actual=np.array([hc[lookup[int(i)]] for i in ids]);error=float(np.abs(actual-expected).max());assert error<2e-5,('Initial hair changed',error)
    if a.preroll:
        for frame in [1-a.preroll,0]:
            s.frame_set(frame);bpy.context.view_layer.update();current=coords(hair);pinned=np.array([current[lookup[int(i)]] for i in ids[hard]])
            assert float(np.abs(pinned-expected[hard]).max())<5e-6,('Preroll attachment moved',frame)
            assert float(np.abs(coords(body)-expected_body[0]).max())<5e-6,('Preroll body moved',frame)
    s.frame_set(1-a.preroll);bpy.context.view_layer.update();cloth.show_viewport=True;cloth.show_render=True
    report=dict(source=str(source),method='Unmodified Blender 5.2.1 Cloth modifier on actual original hair mesh',hair_object=hair.name,body_object=m.name,source_id_attribute='SourceVertexID',hair_vertices=len(hair.data.vertices),hair_polygons=len(hair.data.polygons),pinned_root_vertices=int(hard.sum()),initial_max_error_m=error,original_shape_keys=len(m.data.shape_keys.key_blocks),hair_shape_keys=len(hair.data.shape_keys.key_blocks),quality=20,collision_quality=12,distance_min_m=.003,self_collision=False,frames=[1,a.last],preroll_frames=a.preroll,seams=component_report,references=['https://docs.blender.org/manual/en/latest/physics/cloth/settings/shape.html','https://docs.blender.org/manual/en/latest/physics/cloth/settings/collisions.html'])
    (out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    path=out/'完整角色_原生发片Cloth_15秒.blend';s.frame_start=1-a.preroll;bpy.ops.wm.save_as_mainfile(filepath=str(path))
    def progress(scene,*_):
        if scene.frame_current%15==0:status('BAKING_STOCK_BLENDER_CLOTH',frame=scene.frame_current,last=a.last)
    bpy.app.handlers.frame_change_pre.append(progress);status('BAKING_STOCK_BLENDER_CLOTH',frame=1,last=a.last)
    with bpy.context.temp_override(scene=s,object=hair,active_object=hair,point_cache=pc):bpy.ops.ptcache.bake(bake=True)
    bpy.app.handlers.frame_change_pre.remove(progress);assert pc.is_baked
    s.frame_start=1;s.frame_set(1);bpy.context.view_layer.update();assert pc.is_baked;bpy.ops.wm.save_as_mainfile(filepath=str(path))
    status('BAKED_REQUIRES_ACTUAL_SURFACE_AND_VISUAL_REVIEW',blend=str(path),is_baked=pc.is_baked,**report)
except BaseException as exc:status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
