"""Community classic Cloth workflow on all 27 fitted hair surface proxies.

All dynamics/collision are native. This script configures, samples and caches
the result; it implements no contact projection or motion smoothing.
"""
import argparse,json,sys,time,struct,shutil,traceback,numpy as np
from pathlib import Path
import bpy,bmesh
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.native_hair_surface import asset_path,new_tree,named,group
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=450);p.add_argument('--substeps',type=int,default=20);p.add_argument('--iterations',type=int,default=100);p.add_argument('--body-input',required=True);p.add_argument('--preset',choices=['baseline','soft_rear'],required=True);p.add_argument('--motion-kind',choices=['control','production'],default='control');p.add_argument('--skip-stills',action='store_true');p.add_argument('--contact-mode',choices=['depth','extent_or_depth'],default='depth');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('CLASSIC_LOCAL_FRINGE_SURFACE_PHYSICS',json.dumps(row,ensure_ascii=False),flush=True)
def write_pc2(path,data):
 array=np.asarray(data,dtype='<f4')
 with path.open('wb') as f:f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,array.shape[1],1.,1.,array.shape[0]));f.write(array.tobytes())
try:
 assert not (out/'result.json').exists(),'Fresh run directory required'
 prepared=json.loads((Path(a.prepared)/'setup.json').read_text('utf8'));assert prepared['status']=='FULL_HEAD_LOCAL_FRINGE_SURFACE_READY'
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=prepared['blend'],load_ui=False,use_scripts=False)
 s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.use_preview_range=False;s.render.fps=30;s.tool_settings.use_keyframe_insert_auto=False
 actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();base=repo.parent/'work/headswap_xl_codex';exp=Path(a.body_input);expected=np.load(exp/'body.npy',mmap_mode='r');skinids=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy');inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
 s.frame_set(1);bpy.context.view_layer.update();assert [md.name for md in actor.modifiers if md.type=='SURFACE_DEFORM' and md.name.startswith('Native_SurfaceDeform_') and md.show_viewport and md.show_render]==['Native_SurfaceDeform_FrontHair5-1.L'];initial=coords(actor);proxies=[bpy.data.objects[r['proxy']] for r in prepared['proxies']]
 oldbody=next(ob for ob in bpy.data.objects if any(md.type=='MESH_CACHE' and Path(bpy.path.abspath(md.filepath)).name=='animated_body_collider.pc2' for md in ob.modifiers));oldcache=next(md for md in oldbody.modifiers if md.type=='MESH_CACHE')
 body0=np.array(expected[0]);bm=bmesh.new();[bm.verts.new(v) for v in body0];bm.verts.ensure_lookup_table()
 for f in bf:bm.faces.new([bm.verts[int(i)] for i in f])
 bm.verts.index_update();bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));oriented=[tuple(v.index for v in face.verts) for face in bm.faces];bm.free()
 mesh=bpy.data.meshes.new('ClassicHair_ActualClosedBody');mesh.from_pydata(body0.tolist(),[],oriented);body=bpy.data.objects.new('ClassicHair_ActualClosedBody',mesh);s.collection.objects.link(body);body.hide_render=True
 cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
    if not dst.exists():shutil.copy2(src,dst)
    md.filepath=str(dst)
 md=body.modifiers.new('AnimatedSkin_120Hz','MESH_CACHE');md.cache_format='PC2';md.filepath=oldcache.filepath;md.play_mode='CUSTOM';md.time_mode='FRAME';md.driver_add('eval_frame').driver.expression='(frame-1)*4'
 for f in sorted(set([f for f in [1,16,31,46,61,76,91,226,331,376,526] if f<=a.last]+[a.last])):
  s.frame_set(f);bpy.context.view_layer.update();assert np.max(np.abs(coords(body)-expected[(f-1)*8]))<5e-6,('Collider clock',f)
 s.frame_set(1);bpy.context.view_layer.update()
 body.modifiers.new('ClassicCloth_ActualSkinCollision','COLLISION')
 body.collision.thickness_outer=.003;body.collision.thickness_inner=.001;body.collision.use_culling=False
 colliders=bpy.data.collections.new('ClassicCloth_ActualBodyOnly');s.collection.children.link(colliders);colliders.objects.link(body)
 physical=[];rests=[];motions=[[] for _ in proxies]
 for proxy_index,proxy in enumerate(proxies):
  rests.append(coords(proxy))
  cloth=proxy.modifiers.new('ClassicCloth_NativeSurfacePhysics','CLOTH');settings=cloth.settings
  settings.quality=a.substeps;settings.mass=.005;settings.air_damping=5.;settings.pin_stiffness=1.
  pin=proxy.vertex_groups.new(name='HairRootPinGroup')
  for i,value in enumerate(proxy.data.attributes['HairRootPin'].data):
   if value.value>0:pin.add([i],value.value,'REPLACE')
  settings.vertex_group_mass=pin.name
  assert settings.vertex_group_mass==pin.name and any(x.value>.99 for x in proxy.data.attributes['HairRootPin'].data),('Native pin interface',proxy.name)
  settings.tension_stiffness=1000.;settings.compression_stiffness=1000.;settings.shear_stiffness=1000.;settings.bending_stiffness=25.
  settings.tension_damping=25.;settings.compression_damping=25.;settings.shear_damping=25.
  settings.bending_model='ANGULAR';settings.effector_weights.gravity=1.;settings.use_internal_springs=False
  if a.preset=='soft_rear' and proxy_index in list(range(7,23))+[25,26]:
   settings.bending_model='LINEAR';settings.bending_stiffness=.5;settings.air_damping=1.
   settings.tension_damping=5.;settings.compression_damping=5.;settings.shear_damping=5.
  settings.bending_damping=.5
  row=next(r for r in prepared['proxies'] if r['proxy']==proxy.name)
  settings.use_sewing_springs=bool(row.get('native_sewing_panels'));settings.sewing_force_max=10.
  cloth.collision_settings.collection=colliders;cloth.collision_settings.use_collision=True;cloth.collision_settings.use_self_collision=False
  cloth.collision_settings.distance_min=.002;cloth.collision_settings.collision_quality=12
  cloth.point_cache.frame_start=1;cloth.point_cache.frame_end=a.last;cloth.point_cache.use_disk_cache=False
  physical.append(cloth)
 setup=dict(prepared=prepared['blend'],backend='Unmodified native Blender classic Cloth modifier',surface_proxies=[dict(name=o.name,vertices=len(o.data.vertices),faces=len(o.data.polygons)) for o in proxies],quality=a.substeps,collision_quality=12,tension=1000,compression=1000,shear=1000,bending=25,bending_model='ANGULAR',mass=.005,air_damping=5,gravity=1,body_margin_m=.003,cloth_margin_m=.002,self_collision=False,inter_hair_collision=False,pins='Native Cloth Pin Group; pre-Cloth geometry follows head',original_weights_edited=False,per_frame_corrective_motion=False,user_contact_policy='Only maximum intrusion depth > 5cm stops; connected patch extent is reference only' if a.contact_mode=='depth' else 'Connected embedded extent > 5cm OR depth > 5cm',contact_limit_mode=a.contact_mode,frames_planned=[1,a.last],shutdown_forbidden=True,references=['https://www.bilibili.com/video/BV1cD4y1R7U9?t=195','https://www.bilibili.com/video/BV1pS9MB8Em2?t=176','https://simplicage.readthedocs.io/en/latest/settings.html'],note='Community classic Cloth to original bones workflow; identical physical parameters to previous baseline; only the left fringe uses native Surface Deform; remaining 141 Damped Track bindings unchanged.',geometry_transfer=prepared['display_transfer'],original_bone_lengths_preserved=True,preview_only=True,known_strain_policy='User requests visual preview after accepting stills; record moderate known stretch, stop severe instability and depth >5cm',expected_body_input=str(exp))
 setup.update(control_only=True,preset=a.preset,changed_chain_indices=list(range(7,23))+[25,26] if a.preset=='soft_rear' else [],changed_parameters=dict(bending_model='LINEAR',bending_stiffness=.5,air_damping=1.,spring_damping=5.) if a.preset=='soft_rear' else {},mass_held_constant=.005,structural_stiffness_held_constant=1000.,source_tutorial='BV1cD4y1R7U9 09:12-09:18',scene_gravity=list(s.gravity),scene_use_gravity=s.use_gravity,not_a_production_motion=True)
 setup['note']='Independent full-head controlled turn and stop; original production action preserved. Baseline settings above describe unchanged chains; per_chain_settings records actual overrides.'
 setup['known_strain_policy']='Stop on actual displayed chain P99 edge ratio >1.5 AND maximum edge extension >2cm; stop on intrusion depth >5cm.'
 setup['per_chain_settings']=[dict(chain=prepared['proxies'][j]['chain'],bending_model=m.settings.bending_model,bending_stiffness=m.settings.bending_stiffness,air_damping=m.settings.air_damping,tension_damping=m.settings.tension_damping,mass=m.settings.mass,tension_stiffness=m.settings.tension_stiffness) for j,m in enumerate(physical)]
 setup.update(control_only=a.motion_kind=='control',not_a_production_motion=a.motion_kind=='control',motion_kind=a.motion_kind,keyframe_renders_disabled=a.skip_stills)
 if a.motion_kind=='production':setup['note']='Same native Cloth soft-rear preset evaluated on the untouched production dance; no test head motion.'
 (out/'setup.json').write_text(json.dumps(setup,ensure_ascii=False,indent=2),'utf8');bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_惯性对照_物理配置.blend'))
 # Render an evaluated frozen copy, so still rendering cannot restart an
 # uncached physics graph in the render dependency graph.
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for device in prefs.devices:device.use=device.type=='OPTIX'
 s.cycles.device='GPU';s.cycles.samples=24;s.render.image_settings.color_depth='8';s.render.image_settings.color_mode='RGB';s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.image_settings.file_format='PNG';s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.use_sequencer=False
 def still(frame):
  if a.skip_stills:return
  folder=out/'keyframes';folder.mkdir(exist_ok=True);target=folder/f'f{frame:04d}.png'
  ev=actor.evaluated_get(bpy.context.evaluated_depsgraph_get());data=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());copy=actor.copy();copy.data=data;copy.name='ReviewFrozen_Frame'+str(frame);copy.animation_data_clear();s.collection.objects.link(copy)
  for m in list(copy.modifiers):copy.modifiers.remove(m)
  copy.hide_render=False;actor.hide_render=True
  try:s.render.filepath=str(target);bpy.ops.render.render(write_still=True)
  finally:actor.hide_render=False;bpy.data.objects.remove(copy,do_unlink=True);bpy.data.meshes.remove(data)
  print('CLASSIC_LOCAL_FRINGE_SURFACE_KEYFRAME',frame,str(target),flush=True)
 motion_display=[];motion_proxy=[];motion_rigid=[];tips=[];proxy_tips=[]
 for j,proxy in enumerate(proxies):
  selected=inspection['ids'][inspection['chain_labels']==j];root=np.array(arm.matrix_world@arm.pose.bones[prepared['proxies'][j]['chain']].head);radius=np.linalg.norm(initial[selected]-root,axis=1);tips.append(selected[radius>=np.quantile(radius,.8)])
  qr=np.linalg.norm(rests[j]-root,axis=1);proxy_tips.append(qr>=np.quantile(qr,.8))
 rows=[];stop=None;strain_warnings=[];chain_edges=[np.where((inspection['chain_labels'][inspection['edges'][:,0]]==j)&(inspection['chain_labels'][inspection['edges'][:,1]]==j))[0] for j in range(27)];rest_edges=inspection['edges'];ids=inspection['ids'];l0=np.linalg.norm(initial[ids[rest_edges[:,0]]]-initial[ids[rest_edges[:,1]]],axis=1);valid=l0>.001
 for frame in range(1,a.last+1):
  s.frame_set(frame);bpy.context.view_layer.update();actual=coords(actor);assert np.isfinite(actual).all();bodyerr=float(np.max(np.abs(actual[skinids]-expected[(frame-1)*8])));assert bodyerr<5e-6,('Body changed',frame,bodyerr)
  residuals=[];pin_errors=[]
  for j,proxy in enumerate(proxies):
   q=coords(proxy);assert np.isfinite(q).all() and len(q)==len(proxy.data.vertices);motions[j].append(q.copy());ev=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh()
   attr=data.attributes.get('NativeResidualError');residuals.append(float(attr.data[0].value) if attr and len(attr.data) else None);ev.to_mesh_clear()
   pins=np.array([x.value>.99 for x in proxy.data.attributes['HairRootPin'].data]);matrix=np.array(bpy.data.objects['ClassicHair_HeadMotion'].matrix_world);basepoints=np.array([v.co[:] for v in proxy.data.vertices]);target=basepoints@matrix[:3,:3].T+matrix[:3,3];pin_errors.append(float(np.linalg.norm(q[pins]-target[pins],axis=1).max()))
  delta=np.array(bpy.data.objects['ClassicHair_HeadMotion'].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world)
  motion_display.append(np.array([actual[q].mean(0) for q in tips]));motion_proxy.append(np.array([motions[j][-1][q].mean(0) for j,q in enumerate(proxy_tips)]));motion_rigid.append(np.array([initial[q].mean(0)@delta[:3,:3].T+delta[:3,3] for q in tips]))
  field=ClosedColliderField(actual[skinids],bf);distance,_=field(actual[ids]);contact=embedded_patch_metrics(actual[ids],distance,inspection['edges'],limit_m=.05,limit_mode=a.contact_mode)
  ratio=np.linalg.norm(actual[ids[rest_edges[:,0]]]-actual[ids[rest_edges[:,1]]],axis=1)[valid]/l0[valid]
  row=dict(frame=frame,maximum_depth_m=contact['maximum_depth_m'],maximum_connected_extent_m=contact['maximum_patch_extent_m'],inside_vertices=contact['inside_vertices'],over_5cm=contact['exceeds_limit'],contact_limit_mode=a.contact_mode,extent_over_5cm_reference_only=bool(contact['maximum_patch_extent_m']>.05),body_error_m=bodyerr,maximum_native_pin_error_m=max(pin_errors),native_residual_error=residuals,display_edge_ratio_p01_p99=np.quantile(ratio,[.01,.99]).tolist());rows.append(row)
  if frame==1 or frame%15==1 or frame in [16,31,46,61,76,91] or contact['exceeds_limit']:status('NATIVE_SURFACE_PHYSICS_ACTUAL_HAIR_CHECK',**row)
  if frame==1:row['initial_display_change_m']=float(np.max(np.abs(actual-initial)))
  if frame in [1,16,31,46,61,76,91] or contact['exceeds_limit']:still(frame)
  if contact['exceeds_limit']:
   stop=dict(reason='User 5cm displayed hair intrusion depth limit exceeded' if a.contact_mode=='depth' else 'User 5cm displayed hair contact limit exceeded',worst_patch=contact['patches'][0],**row);break
  fullratio=np.ones(len(l0));fullratio[valid]=ratio;edgechange=(fullratio-1)*l0
  stretched=[dict(chain=prepared['proxies'][j]['chain'],p99=float(np.quantile(fullratio[inds],.99)),maximum_edge_extension_m=float(edgechange[inds].max())) for j,inds in enumerate(chain_edges) if len(inds) and np.quantile(fullratio[inds],.99)>1.5 and edgechange[inds].max()>.02]
  row['stretched_chains']=stretched
  if stretched:
   strain_warnings.append(dict(frame=frame,chains=stretched))
   stop=dict(reason='Actual displayed hair stretches during native hair motion',**row)
   status('STOPPING_DISPLAY_HAIR_STRETCH_CHECK',**row)
   (out/'stop_detection.json').write_text(json.dumps(stop,ensure_ascii=False,indent=2),'utf8')
   still(frame);break
 # Preserve direct native output as display caches; not resumable solver state.
 for j,(proxy,mod) in enumerate(zip(proxies,physical)):
  path=cache/('ClassicHair_'+str(j).zfill(2)+'.pc2');write_pc2(path,motions[j])
  for m in proxy.modifiers:m.show_viewport=False;m.show_render=False
  replay=proxy.modifiers.new('BakedNativeSurface_ActualPhysics','MESH_CACHE');replay.cache_format='PC2';replay.filepath=str(path);replay.play_mode='CUSTOM';replay.time_mode='FRAME';replay.driver_add('eval_frame').driver.expression='frame-1'
  bpy.context.view_layer.update()
  if np.max(np.abs(coords(proxy)-motions[j][-1]))>5e-6:raise RuntimeError('Native surface cache replay mismatch')
 np.savez_compressed(out/'inertia_tip_motion.npz',display=np.asarray(motion_display),proxy=np.asarray(motion_proxy),rigid=np.asarray(motion_rigid),frames=np.arange(1,frame+1))
 publication=dict(published_through_frame=frame,run=str(out));(out/'publication.json').write_text(json.dumps(publication),'utf8');s['FullHairCachePublication']=str(out/'publication.json');s['UserHairContactLimitCM']=5.;s['ShutdownForbidden']=True;s['ReviewAllHairCollisionSolved']=False;s.frame_end=frame
 blend=out/('完整角色_惯性对照_物理缓存.blend' if a.motion_kind=='control' else '完整角色_柔顺后发_原舞蹈物理缓存.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 result=dict(status=('INERTIA_CONTROL_STOPPED_CONTACT_OR_STRETCH' if stop else 'INERTIA_CONTROL_91_FRAMES_COMPLETED') if a.motion_kind=='control' else ('PRODUCTION_SOFT_REAR_STOPPED_CONTACT_OR_STRETCH' if stop else 'PRODUCTION_SOFT_REAR_NATIVE_FRAMES_COMPLETED'),contact_limit_mode=a.contact_mode,control_only=a.motion_kind=='control',preset=a.preset,preview_only=True,not_a_physics_acceptance_certificate=True,known_strain_warnings=strain_warnings,blend=str(blend),frames=[1,frame],stop=stop,samples=rows,all_hair_collision_solved=False,actual_hair_surface_checked=True,original_materials_preserved=True,body_and_hug_motion_preserved=True,original_weights_edited=False,physics='Native classic Blender Cloth modifier, no source changes',geometry_transfer=prepared['display_transfer'],display_cache_is_solver_checkpoint=False,shutdown_forbidden=True)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');status(result['status'],frame=frame,stop=stop,blend=str(blend))
except BaseException as exc:status('SCRIPT_INTERFACE_OR_PHYSICS_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
