"""Rebake only the two cheek locks with the unchanged upstream Jiggle addon.

All other hair animation and protected body motion are preserved. Simulate
the continuous original 1..450 interval, publish only original frames 151..450.
"""
import argparse,importlib.util,json,re,shutil,sys,time,traceback,hashlib
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--precise-body',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out);out.mkdir(parents=True,exist_ok=True);base=repo.parent/'work/headswap_xl_codex'
src=base/'normal_preview15_20261101/完整角色_现有最佳流程_15秒预览.blend'
started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw)
 temp=out/'status.tmp.json';temp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');temp.replace(out/'status.json');print(json.dumps(row,ensure_ascii=False),flush=True)
def curves(action):
 return [fc for layer in action.layers for strip in layer.strips for bag in getattr(strip,'channelbags',[]) for fc in bag.fcurves]
def retime(fc,factor):
 for pt in fc.keyframe_points:
  pt.co.x=1+(pt.co.x-1)*factor;pt.handle_left.x=1+(pt.handle_left.x-1)*factor;pt.handle_right.x=1+(pt.handle_right.x-1)*factor
 fc.update()
try:
 assert not (out/'setup.json').exists(),'Use a new output directory'
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
 prov=json.loads((base/'jiggle_physics_20261031/plugin_provenance.json').read_text('utf8'));pluginpath=Path(prov['source_dir'])/'__init__.py'
 spec=importlib.util.spec_from_file_location('jiggle_official',pluginpath,submodule_search_locations=[str(pluginpath.parent)])
 plugin=importlib.util.module_from_spec(spec);sys.modules[spec.name]=plugin;spec.loader.exec_module(plugin);plugin.register()
 s=bpy.context.scene;arm=bpy.data.objects['东雪莲x达妮娅_骨架'];obj=bpy.data.objects['东雪莲x达妮娅_素体']
 s.frame_start=1;s.frame_end=450;s.use_preview_range=False;s.tool_settings.use_keyframe_insert_auto=False
 s.jiggle.enable=False;arm.jiggle.freeze=True
 targets={f'Sidehair{i}.{side}' for i in range(1,8) for side in ['L','R']};assert targets.issubset(arm.pose.bones.keys())
 unaffected=[b.name for b in arm.pose.bones if b.name not in targets];checkframes=[1,151,234,256,310,321,331,380,450]
 def snapshot():return np.asarray([np.array(arm.pose.bones[n].matrix) for n in unaffected])
 before={}
 for f in checkframes:s.frame_set(f);bpy.context.view_layer.update();before[f]=snapshot()
 # Clone the prior completed bake. The original action stays in the file.
 oldaction=arm.animation_data.action;oldaction.use_fake_user=True;arm.animation_data.action=oldaction.copy();action=arm.animation_data.action
 action.name='JigglePhysics_两侧短发_缩小碰撞壳并增加阻尼'
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in list(bag.fcurves):
     if any(fc.data_path.startswith('pose.bones['+json.dumps(n)+']') for n in targets):bag.fcurves.remove(fc)
 s.frame_set(1);bpy.context.view_layer.update();enabled={b.name:b.jiggle.enable for b in arm.pose.bones};settings=[]
 for b in arm.pose.bones:b.jiggle.enable=False
 precise_collection=None
 if a.precise_body:
  body_colliders=[ob for ob in bpy.data.objects if ob.type=='MESH' and any(md.type=='MESH_CACHE' and Path(bpy.path.abspath(md.filepath)).name=='animated_body_collider.pc2' for md in ob.modifiers)]
  assert len(body_colliders)==1,[ob.name for ob in body_colliders]
  precise_collection=bpy.data.collections.new('ShortSidehair_ExactAnimatedBody');s.collection.children.link(precise_collection);precise_collection.objects.link(body_colliders[0])
 for name in sorted(targets):
  b=arm.pose.bones[name];old={k:getattr(b,'jiggle_'+k) for k in ['collision_radius','angle_elasticity','air_drag','friction','elasticity_soften']}
  b.rotation_mode='QUATERNION';b.location=(0,0,0);b.rotation_quaternion=(1,0,0,0);b.scale=(1,1,1)
  for prop in ['location','rotation_quaternion','scale']:b.keyframe_insert(data_path=prop,frame=1,group=b.name)
  b.jiggle.enable=not name.startswith('Sidehair1.');b.bone.hide=False;b.bone.hide_select=False
  b.jiggle_collision_radius=.006;b.jiggle_angle_elasticity=.88;b.jiggle_elasticity_soften=.15
  b.jiggle_root_elasticity=1.;b.jiggle_length_elasticity=1.;b.jiggle_air_drag=.4;b.jiggle_friction=.65;b.jiggle_blend=1.;b.jiggle_gravity=.25
  if precise_collection:b.jiggle.collider_type='Collection';b.jiggle.collider_collection=precise_collection
  settings.append(dict(bone=name,previous=old,collision_radius_m=.006,angle_elasticity=.88,elasticity_soften=.15,air_drag=.4,friction=.65,fixed_root=not b.jiggle.enable))
 # Duplicate external caches to make the revision independently reopenable.
 retained=[];(out/'cache').mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    original=Path(bpy.path.abspath(md.filepath));assert original.exists(),str(original)
    target=out/'cache'/original.name;shutil.copy2(original,target);md.filepath=str(target)
    retained.append(dict(object=ob.name,path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size))
 for im in bpy.data.images:
  if im.filepath and im.source in {'FILE','MOVIE','SEQUENCE','TILED'}:im.filepath=bpy.path.abspath(im.filepath)
 # Same 120 Hz integration used by the completed full-head bake. Retime both
 # the unaffected native action and NLA/cache clocks, then restore exactly.
 factor=4;stripstates=[];cachestates=[];drivers=[]
 for fc in curves(action):retime(fc,factor)
 for track in arm.animation_data.nla_tracks:
  for strip in track.strips:
   state={k:getattr(strip,k) for k in ['frame_start','frame_end','action_frame_start','action_frame_end','scale','blend_in','blend_out']};stripstates.append((strip,state))
   strip.frame_start=1+(state['frame_start']-1)*factor;strip.scale=state['scale']*factor;strip.blend_in=state['blend_in']*factor;strip.blend_out=state['blend_out']*factor
   for fc in strip.fcurves:retime(fc,factor)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    cachestates.append((md,md.frame_start,md.frame_scale));md.frame_start=1+(md.frame_start-1)*factor;md.frame_scale*=factor
    if md.play_mode=='CUSTOM' and ob.animation_data:
     path=md.path_from_id('eval_frame')
     for fc in ob.animation_data.drivers:
      if fc.data_path==path:
       drivers.append((fc.driver,fc.driver.expression));fc.driver.expression=re.sub(r'\bframe\b',f'(1+(frame-1)/{factor})',fc.driver.expression)
 s.frame_end=1797;s.render.fps=120
 for f,expected in before.items():
  s.frame_set(1+(f-1)*factor);bpy.context.view_layer.update();assert np.max(np.abs(snapshot()-expected))<2e-5,('retime',f)
 arm.jiggle.enable=True;arm.jiggle.mute=False;arm.jiggle.freeze=False;s.jiggle.enable=True
 s.jiggle.bake_overwrite=True;s.jiggle.bake_nla=False;s.jiggle.preroll=120;s.jiggle.loop=False
 bpy.ops.object.select_all(action='DESELECT');arm.hide_set(False);arm.hide_viewport=False;arm.select_set(True);bpy.context.view_layer.objects.active=arm;s.frame_set(1)
 def progress(scene,*_):
  if scene.frame_current%120==0:status('UPSTREAM_PLUGIN_REBAKING_TWO_SHORT_LOCKS',simulation_frame=scene.frame_current,original_frame=1+(scene.frame_current-1)/4)
 bpy.app.handlers.frame_change_pre.append(progress);bpy.ops.object.mode_set(mode='POSE');status('UPSTREAM_PLUGIN_REBAKING_TWO_SHORT_LOCKS',simulation_frame=1)
 assert bpy.ops.armature.jiggle_bake()=={'FINISHED'}
 bpy.app.handlers.frame_change_pre.remove(progress);bpy.ops.object.mode_set(mode='OBJECT');s.jiggle.enable=False;arm.jiggle.freeze=True
 for fc in curves(action):retime(fc,1/factor)
 for strip,state in stripstates:
  strip.frame_start=state['frame_start'];strip.scale=state['scale'];strip.blend_in=state['blend_in'];strip.blend_out=state['blend_out']
  for fc in strip.fcurves:retime(fc,1/factor)
 for md,start,scale in cachestates:md.frame_start=start;md.frame_scale=scale
 for driver,expression in drivers:driver.expression=expression
 for b in arm.pose.bones:
  if b.name not in targets:b.jiggle.enable=enabled[b.name]
 s.render.fps=30;s.render.fps_base=1.;errors=[]
 for f,expected in before.items():
  s.frame_set(f);bpy.context.view_layer.update();error=float(np.max(np.abs(snapshot()-expected)));errors.append(dict(frame=f,max_non_target_bone_matrix_error=error));assert error<2e-5,('unaffected animation',f,error)
 s.frame_start=151;s.frame_end=450;s.frame_set(151);s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.use_sequencer=False
 s['ReviewAllHairCollisionSolved']=False;s['ShutdownForbidden']=True;s['ShortSidehairRevision']='upstream Jiggle 120Hz, fixed attachment, 6mm collision radius, angle .88, air drag .4, friction .65'
 blend=out/'完整角色_侧发阻尼修正_原片5至15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 report=dict(status='TWO_SHORT_LOCKS_UPSTREAM_REBAKE_READY_FOR_VISUAL_REVIEW',blend=str(blend),source_blend=str(src),frames=[151,450],simulation_source_frames=[1,450],simulation_fps=120,fps=30,resolution=[1920,1080],duration_seconds=10,audio_seek_seconds=5.0666666667,plugin=prov,plugin_file_sha256=hashlib.sha256(pluginpath.read_bytes()).hexdigest(),target_bones=settings,short_locks_collider_mode='exact animated body mesh' if precise_collection else 'inherited ellipsoids',all_other_bones_preserved=errors,retained_caches=retained,all_hair_collision_solved=False,no_custom_solver_or_motion_filter=True,shutdown_forbidden=True)
 (out/'setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');status('REBAKE_COMPLETE_REQUIRES_VISUAL_REVIEW',blend=str(blend))
except BaseException as exc:status('FAILED_SCRIPT_OR_BAKE',error=repr(exc),traceback=traceback.format_exc());raise
