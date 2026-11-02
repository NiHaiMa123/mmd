"""Unchanged Blender Cloth Dynamics asset on two fitted surface proxies.

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
p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--out',required=True);p.add_argument('--last',type=int,default=450);p.add_argument('--substeps',type=int,default=20);p.add_argument('--iterations',type=int,default=100);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');tmp.replace(out/'status.json');print('SIDE_SURFACE_PHYSICS',json.dumps(row,ensure_ascii=False),flush=True)
def write_pc2(path,data):
 array=np.asarray(data,dtype='<f4')
 with path.open('wb') as f:f.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,array.shape[1],1.,1.,array.shape[0]));f.write(array.tobytes())
try:
 assert not (out/'result.json').exists(),'Fresh run directory required'
 prepared=json.loads((Path(a.prepared)/'setup.json').read_text('utf8'));assert prepared['status']=='TWO_SIDE_SURFACE_PROXIES_BOUND_NOT_PHYSICS_ACCEPTED'
 probe=json.loads((repo.parent/'work/headswap_xl_codex/side_surface_20261101/pin_motion_probe/result.json').read_text('utf8'));assert not probe['selected_zero_mass_pins']
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=prepared['blend'],load_ui=False,use_scripts=False)
 s=bpy.context.scene;s.frame_start=1;s.frame_end=a.last;s.use_preview_range=False;s.render.fps=30;s.tool_settings.use_keyframe_insert_auto=False
 actor=bpy.data.objects['东雪莲x达妮娅_素体'];base=repo.parent/'work/headswap_xl_codex';exp=base/'fullhair_repro_20261030/input_body_aware';expected=np.load(exp/'body.npy',mmap_mode='r');skinids=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy');inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')
 s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor);proxies=[bpy.data.objects[r['proxy']] for r in prepared['proxies']]
 oldbody=next(ob for ob in bpy.data.objects if any(md.type=='MESH_CACHE' and Path(bpy.path.abspath(md.filepath)).name=='animated_body_collider.pc2' for md in ob.modifiers));oldcache=next(md for md in oldbody.modifiers if md.type=='MESH_CACHE')
 body0=np.array(expected[0]);bm=bmesh.new();[bm.verts.new(v) for v in body0];bm.verts.ensure_lookup_table()
 for f in bf:bm.faces.new([bm.verts[int(i)] for i in f])
 bm.verts.index_update();bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));oriented=[tuple(v.index for v in face.verts) for face in bm.faces];bm.free()
 mesh=bpy.data.meshes.new('SideSurface_ActualClosedBody');mesh.from_pydata(body0.tolist(),[],oriented);body=bpy.data.objects.new('SideSurface_ActualClosedBody',mesh);s.collection.objects.link(body);body.hide_render=True
 cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
    if not dst.exists():shutil.copy2(src,dst)
    md.filepath=str(dst)
 md=body.modifiers.new('AnimatedSkin_120Hz','MESH_CACHE');md.cache_format='PC2';md.filepath=oldcache.filepath;md.play_mode='CUSTOM';md.time_mode='FRAME';md.driver_add('eval_frame').driver.expression='(frame-1)*4'
 for f in [1,201,226,376,450]:
  s.frame_set(f);bpy.context.view_layer.update();assert np.max(np.abs(coords(body)-expected[(f-1)*8]))<5e-6,('Collider clock',f)
 s.frame_set(1);bpy.context.view_layer.update()
 with bpy.data.libraries.load(str(asset_path()),link=False) as (src,dst):dst.node_groups=['Cloth Dynamics (Experimental)','Collider']
 clothasset,colliderasset=dst.node_groups;physical=[];rests=[];motions=[[] for _ in proxies]
 for proxy in proxies:
  rest=coords(proxy);rests.append(rest)
  tree,inp,output=new_tree('SideSurface_NativePhysics_'+proxy.name);links=tree.links;info=tree.nodes.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=body
  coll=group(tree,colliderasset);coll.inputs['Deforming'].default_value=True;coll.inputs['Edge Contacts'].default_value=True;coll.inputs['Margin'].default_value=.003;coll.inputs['Friction'].default_value=.2;links.new(info.outputs['Geometry'],coll.inputs['Geometry'])
  bundle=tree.nodes.new('NodeCombineBundle');item=bundle.bundle_items.new('BUNDLE','ActualBody');links.new(coll.outputs['Collider'],bundle.inputs[item.name])
  cloth=group(tree,clothasset);links.new(inp.outputs['Geometry'],cloth.inputs['Geometry']);links.new(named(tree,'HairRootPin'),cloth.inputs['Pin Group']);links.new(bundle.outputs['Bundle'],cloth.inputs['Effectors'])
  cloth.inputs['Stretchiness'].default_value=0.;cloth.inputs['Bendiness'].default_value=.025;cloth.inputs['Substeps'].default_value=a.substeps;cloth.inputs['Constraint Steps'].default_value=a.iterations;cloth.inputs['Collision Radius'].default_value=.001;cloth.inputs['Linear Damping'].default_value=5.;cloth.inputs['Mass'].default_value=.01
  next(x for x in cloth.inputs if x.name=='Gravity' and x.type=='BOOLEAN').default_value=False
  for socket in cloth.inputs:
   if socket.type=='BOOLEAN' and 'tear' in socket.name.lower():socket.default_value=False
  residual=next((x for x in cloth.outputs if x.name.lower().replace(' ','')=='residualerror'),None)
  if residual:
   store=tree.nodes.new('GeometryNodeStoreNamedAttribute');store.data_type='FLOAT';store.domain='POINT';store.inputs['Name'].default_value='NativeResidualError';links.new(cloth.outputs['Geometry'],store.inputs['Geometry']);links.new(residual,store.inputs['Value']);links.new(store.outputs['Geometry'],output.inputs['Geometry'])
  else:links.new(cloth.outputs['Geometry'],output.inputs['Geometry'])
  mod=proxy.modifiers.new('Native_Cloth_SurfacePhysics','NODES');mod.node_group=tree
  for bake in mod.bakes:bake.use_custom_simulation_frame_range=True;bake.frame_start=1;bake.frame_end=a.last
  physical.append(mod)
 setup=dict(prepared=prepared['blend'],backend='Unmodified bundled Blender 5.2.1 Cloth Dynamics / XPBD mesh',asset=str(asset_path()),surface_proxies=[dict(name=o.name,vertices=len(o.data.vertices),faces=len(o.data.polygons)) for o in proxies],substeps=a.substeps,iterations=a.iterations,stretchiness=0,bendiness=.025,collision_radius_m=.001,body_margin_m=.003,edge_contacts=True,gravity=False,linear_damping=5,pins='Native Pin Group with normal positive mass, moving attachment verified',self_collision=False,original_weights_edited=False,per_frame_corrective_motion=False,user_contact_policy='Connected embedded extent > 5cm OR depth > 5cm; otherwise record and continue',frames_planned=[1,a.last],shutdown_forbidden=True)
 (out/'setup.json').write_text(json.dumps(setup,ensure_ascii=False,indent=2),'utf8');bpy.ops.wm.save_as_mainfile(filepath=str(out/'完整角色_原生薄面物理配置_未烘焙.blend'))
 # Render an evaluated frozen copy, so still rendering cannot restart an
 # uncached physics graph in the render dependency graph.
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for device in prefs.devices:device.use=device.type=='OPTIX'
 s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.image_settings.file_format='PNG';s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.use_sequencer=False
 def still(frame):
  folder=out/'keyframes';folder.mkdir(exist_ok=True);target=folder/f'f{frame:04d}.png'
  ev=actor.evaluated_get(bpy.context.evaluated_depsgraph_get());data=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());copy=actor.copy();copy.data=data;copy.name='ReviewFrozen_Frame'+str(frame);copy.animation_data_clear();s.collection.objects.link(copy)
  for m in list(copy.modifiers):copy.modifiers.remove(m)
  copy.hide_render=False;actor.hide_render=True
  try:s.render.filepath=str(target);bpy.ops.render.render(write_still=True)
  finally:actor.hide_render=False;bpy.data.objects.remove(copy,do_unlink=True);bpy.data.meshes.remove(data)
  print('SIDE_SURFACE_KEYFRAME',frame,str(target),flush=True)
 rows=[];stop=None;rest_edges=inspection['edges'];ids=inspection['ids'];l0=np.linalg.norm(initial[ids[rest_edges[:,0]]]-initial[ids[rest_edges[:,1]]],axis=1);valid=l0>.001
 for frame in range(1,a.last+1):
  s.frame_set(frame);bpy.context.view_layer.update();actual=coords(actor);assert np.isfinite(actual).all();bodyerr=float(np.max(np.abs(actual[skinids]-expected[(frame-1)*8])));assert bodyerr<5e-6,('Body changed',frame,bodyerr)
  residuals=[];pin_errors=[]
  for j,proxy in enumerate(proxies):
   q=coords(proxy);assert np.isfinite(q).all() and len(q)==len(proxy.data.vertices);motions[j].append(q.copy());ev=proxy.evaluated_get(bpy.context.evaluated_depsgraph_get());data=ev.to_mesh()
   attr=data.attributes.get('NativeResidualError');residuals.append(float(attr.data[0].value) if attr and len(attr.data) else None);ev.to_mesh_clear()
  field=ClosedColliderField(actual[skinids],bf);distance,_=field(actual[ids]);contact=embedded_patch_metrics(actual[ids],distance,inspection['edges'],limit_m=.05)
  ratio=np.linalg.norm(actual[ids[rest_edges[:,0]]]-actual[ids[rest_edges[:,1]]],axis=1)[valid]/l0[valid]
  row=dict(frame=frame,maximum_depth_m=contact['maximum_depth_m'],maximum_connected_extent_m=contact['maximum_patch_extent_m'],inside_vertices=contact['inside_vertices'],over_5cm=contact['exceeds_limit'],body_error_m=bodyerr,native_residual_error=residuals,display_edge_ratio_p01_p99=np.quantile(ratio,[.01,.99]).tolist());rows.append(row)
  if frame==1 or frame%15==1 or frame in [201,226,376,450] or contact['exceeds_limit']:status('NATIVE_SURFACE_PHYSICS_ACTUAL_HAIR_CHECK',**row)
  if frame==1:row['initial_display_change_m']=float(np.max(np.abs(actual-initial)))
  if frame in [1,201,226,376,450] or contact['exceeds_limit']:still(frame)
  if contact['exceeds_limit']:
   stop=dict(reason='User 5cm displayed hair contact limit exceeded',worst_patch=contact['patches'][0],**row);break
  if np.quantile(ratio,.99)>2:
   stop=dict(reason='Actual hair has widespread visible stretching',**row);break
 # Preserve direct native output as display caches; not resumable solver state.
 for j,(proxy,mod) in enumerate(zip(proxies,physical)):
  path=cache/('SideSurface_'+str(j)+'.pc2');write_pc2(path,motions[j])
  for m in proxy.modifiers:m.show_viewport=False;m.show_render=False
  replay=proxy.modifiers.new('BakedNativeSurface_ActualPhysics','MESH_CACHE');replay.cache_format='PC2';replay.filepath=str(path);replay.play_mode='CUSTOM';replay.time_mode='FRAME';replay.driver_add('eval_frame').driver.expression='frame-1'
  bpy.context.view_layer.update()
  if np.max(np.abs(coords(proxy)-motions[j][-1]))>5e-6:raise RuntimeError('Native surface cache replay mismatch')
 publication=dict(published_through_frame=frame,run=str(out));(out/'publication.json').write_text(json.dumps(publication),'utf8');s['FullHairCachePublication']=str(out/'publication.json');s['UserHairContactLimitCM']=5.;s['ShutdownForbidden']=True;s['ReviewAllHairCollisionSolved']=False;s.frame_end=frame
 blend=out/'完整角色_两侧薄面原生物理_复查.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 result=dict(status='STOPPED_NATIVE_SURFACE_CONTACT_OR_STRETCH' if stop else 'NATIVE_SURFACE_450_FRAMES_WITHIN_USER_5CM_LIMIT',blend=str(blend),frames=[1,frame],stop=stop,samples=rows,all_hair_collision_solved=False,actual_hair_surface_checked=True,original_materials_preserved=True,body_and_hug_motion_preserved=True,original_weights_edited=False,physics='Bundled Blender Cloth Dynamics, no source changes',geometry_transfer='Native Surface Deform on original scoped vertices',display_cache_is_solver_checkpoint=False,shutdown_forbidden=True)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');status(result['status'],frame=frame,stop=stop,blend=str(blend))
except BaseException as exc:status('SCRIPT_INTERFACE_OR_PHYSICS_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
