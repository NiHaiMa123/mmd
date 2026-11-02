"""Configure the published MMD Tools Append converter and native Cloth bake."""
import argparse,importlib,json,shutil,struct,sys,time,traceback
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--bake',action='store_true');p.add_argument('--last',type=int,default=450)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
research=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031';start=time.monotonic()
def status(stage,**kw):
    d=dict(stage=stage,elapsed_s=time.monotonic()-start,**kw);q=out/'status.tmp.json';q.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8');q.replace(out/'status.json');print('APPEND_CLOTH',json.dumps(d,ensure_ascii=False),flush=True)
try:
    status('OPENING_COMPLETE_PREPARED_SCENE')
    engine('import_export').ensure_mmd_tools()
    bpy.ops.wm.open_mainfile(filepath=str(research/'candidate10/完整角色_Jiggle配置_未烘焙.blend'),load_ui=False,use_scripts=False)
    s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.render.fps=30;s.use_preview_range=False
    m=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];s.frame_set(1);bpy.context.view_layer.update()
    initial=coords(m);config=json.loads((research/'candidate10/configuration.json').read_text('utf8'));names={r['name'] for r in config['hair_bones']}
    # Bake an independent native FK attachment before adding the converter's
    # hair constraints. Copy-Transforms back to this same hair rig forms an
    # armature/guide dependency cycle, even when only the head is requested.
    source_head_length=arm.pose.bones['頭'].length;source_arm_world=arm.matrix_world.copy();head_samples=[]
    for f in np.arange(1,a.last+.01,.125):
        s.frame_set(int(f),subframe=float(f%1));bpy.context.view_layer.update();head_samples.append((float(f),arm.pose.bones['頭'].matrix.copy()))
    s.frame_set(1);bpy.context.view_layer.update()
    prov=json.loads((research/'append_reference/provenance.json').read_text('utf8'));sys.path.insert(0,prov['source_dir'])
    package=importlib.import_module('mmd_tools_append')
    converter=importlib.import_module('mmd_tools_append.converters.physics.rigid_body_to_cloth')
    cloth_module=importlib.import_module('mmd_tools_append.converters.physics.cloth')
    util=importlib.import_module('mmd_tools_append.utilities')
    mmd=next(mod for name,mod in list(sys.modules.items()) if name.endswith('mmd_tools') and hasattr(mod,'core') and hasattr(mod.core,'model'))
    util._MMD_TOOLS_CACHE=mmd;cloth_module.on_import_mmd_tools_ensure_cloth_methods(mmd)
    root=mmd.core.model.FnModel.find_root_object(m)
    rigids=[o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY' and o.mmd_rigid.bone in names]
    assert len(rigids)==len(names),(len(rigids),len(names))
    bpy.ops.object.select_all(action='DESELECT');m.hide_set(False);m.select_set(True);bpy.context.view_layer.objects.active=m
    status('CALLING_UNMODIFIED_OFFICIAL_CONVERTER',hair_rigid_bodies=len(rigids),mode='BONE_CONSTRAINT')
    converter.RigidBodyToClothConverter.convert(root,rigids,[m],0,0.,converter.PhysicsMode.BONE_CONSTRAINT,True,False)
    cloth_objects=[o for o in bpy.data.objects if any(mod.type=='CLOTH' for mod in o.modifiers)]
    assert len(cloth_objects)==1,[o.name for o in cloth_objects]
    proxy=cloth_objects[0];cloth=next(mod for mod in proxy.modifiers if mod.type=='CLOTH')
    # Normalize the attachment rig to the already-posed first frame. The native
    # Armature modifier then sees identity deformation on frame 1, avoiding a
    # second application of the head's starting pose to the converter's pins.
    head_matrix=head_samples[0][1]
    driver_data=bpy.data.armatures.new('Cloth_Attachment_InitialPoseRest');driver=bpy.data.objects.new('Cloth_头部附着驱动',driver_data);s.collection.objects.link(driver);driver.matrix_world=source_arm_world;driver.hide_render=True
    bpy.ops.object.select_all(action='DESELECT');driver.select_set(True);bpy.context.view_layer.objects.active=driver
    bpy.ops.object.mode_set(mode='EDIT');bone=driver_data.edit_bones.new('頭');bone.matrix=head_matrix;bone.length=source_head_length;bpy.ops.object.mode_set(mode='OBJECT')
    pose=driver.pose.bones['頭'];pose.rotation_mode='QUATERNION'
    for f,matrix in head_samples:
        pose.matrix=matrix
        for prop in ['location','rotation_quaternion','scale']:pose.keyframe_insert(data_path=prop,frame=f,group='頭')
    driver.animation_data.action.name='Cloth_Attachment_源头部动作原生FK烘焙'
    for mod in proxy.modifiers:
        if mod.type=='ARMATURE':mod.object=driver
    s.frame_set(1);bpy.context.view_layer.update()
    body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部']
    cm=next(md for md in body.modifiers if md.type=='MESH_CACHE')
    with Path(bpy.path.abspath(cm.filepath)).open('rb') as stream:
        _,_,_,first,step,_=struct.unpack('<12siiffi',stream.read(32))
    cm.play_mode='CUSTOM';cm.time_mode='FRAME';cm.driver_add('eval_frame').driver.expression=f'(frame - {first:.17g}) / {step:.17g}'
    body.modifiers.new('Native_Cloth_Body_Collision','COLLISION');body.collision.thickness_outer=.004;body.collision.thickness_inner=.001
    collection=bpy.data.collections.new('Append_仅身体碰撞');s.collection.children.link(collection);collection.objects.link(body)
    cloth.collision_settings.collection=collection;cloth.collision_settings.use_collision=True;cloth.collision_settings.use_self_collision=False
    body.collision.use_culling=False
    cloth.collision_settings.distance_min=.025;cloth.collision_settings.collision_quality=16
    cloth.settings.quality=32;cloth.settings.mass=.005;cloth.settings.air_damping=5
    cloth.settings.tension_stiffness=1000;cloth.settings.compression_stiffness=1000;cloth.settings.shear_stiffness=1000;cloth.settings.bending_stiffness=50
    cache=out/'cache';cache.mkdir(exist_ok=True)
    for obj in bpy.data.objects:
        for mod in obj.modifiers:
            if mod.type=='MESH_CACHE':
                source=Path(bpy.path.abspath(mod.filepath));target=cache/source.name
                if not target.exists():shutil.copy2(source,target)
                mod.filepath=str(target)
    pc=cloth.point_cache;pc.frame_start=1;pc.frame_end=a.last;pc.use_disk_cache=True
    cloth.show_viewport=False;cloth.show_render=False
    expected_body=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r');errors=[]
    for frame in range(1,a.last+1):
        s.frame_set(frame);bpy.context.view_layer.update();errors.append(float(np.abs(coords(body)-expected_body[(frame-1)*8]).max()))
    assert max(errors)<5e-6,('Physical body is out of time',max(errors))
    (out/'body_cache_replay.json').write_text(json.dumps(dict(frames=a.last,max_error_m=max(errors),cache_sample_step=step),indent=2),'utf8')
    cloth.show_viewport=True;cloth.show_render=True
    s.frame_set(1);bpy.context.view_layer.update()
    path=out/'完整角色_MMDToolsAppend_头发布料_15秒.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    report=dict(plugin=prov,source=str(research/'candidate10/完整角色_Jiggle配置_未烘焙.blend'),converter_mode='BONE_CONSTRAINT',proxy=proxy.name,proxy_vertices=len(proxy.data.vertices),proxy_faces=len(proxy.data.polygons),hair_bones=len(names),original_shape_keys=len(m.data.shape_keys.key_blocks),body_only_collision=True,self_collision=False,frames=[1,a.last],initial_render_mesh_change_m=float(np.abs(coords(m)-initial).max()),plugin_source_modified=False)
    (out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    if a.bake:
        def progress(scene,*_):
            if scene.frame_current%30==0:status('BAKING_NATIVE_CLOTH',frame=scene.frame_current,last=a.last)
        bpy.app.handlers.frame_change_pre.append(progress)
        bpy.ops.object.select_all(action='DESELECT');proxy.hide_set(False);proxy.hide_viewport=False;proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
        status('BAKING_NATIVE_CLOTH',frame=1,last=a.last)
        with bpy.context.temp_override(scene=s,object=proxy,active_object=proxy,point_cache=pc):bpy.ops.ptcache.bake(bake=True)
        bpy.app.handlers.frame_change_pre.remove(progress)
        assert pc.is_baked,'Native Cloth cache did not bake'
        s.frame_set(1);bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(path))
    status('NATIVE_CLOTH_BAKED_REQUIRES_REVIEW' if a.bake else 'CONFIGURED_REQUIRES_REVIEW',blend=str(path),is_baked=pc.is_baked,**report)
except BaseException as exc:
    status('FAILED',error=repr(exc),traceback=traceback.format_exc());raise
