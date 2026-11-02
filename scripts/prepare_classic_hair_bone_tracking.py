"""Native triangle-parent goals -> Damped Track -> original MMD skin weights.

Only rest binding is computed here. There is no custom dynamics, per-frame
pose editing, contact projection, bone scaling, or surface deformation.
"""
import argparse,json,sys,shutil,time,traceback
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--prepared',required=True);p.add_argument('--previous',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);(out/'status.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');print('BONE_TRACKING_PREP',json.dumps(row,ensure_ascii=False),flush=True)
try:
 assert not (out/'setup.json').exists(),'Fresh preparation directory required'
 prepared=json.loads((Path(a.prepared)/'setup.json').read_text('utf8'));base=repo.parent/'work/headswap_xl_codex';inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=prepared['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
 surface=[md for md in actor.modifiers if md.type=='SURFACE_DEFORM' and md.name.startswith('Native_SurfaceDeform_')]
 assert len(surface)==27
 for md in surface:md.show_viewport=False;md.show_render=False
 bpy.context.view_layer.update();initial=coords(actor);goals=[];constraints=[];bindings=[]
 # Parenting to an evaluated triangle preserves a tail's rest offset from
 # the simulated surface. Original bone lengths and hierarchy are retained.
 for row,chain in zip(prepared['proxies'],meta['chains']):
  assert row['chain']==chain['name'];proxy=bpy.data.objects[row['proxy']];points=coords(proxy);proxy.data.calc_loop_triangles();faces=[tuple(t.vertices) for t in proxy.data.loop_triangles];tree=BVHTree.FromPolygons(points.tolist(),faces,all_triangles=True)
  for name in chain['bones']:
   bone=arm.pose.bones[name];tail=arm.matrix_world@bone.tail;_,_,fi,distance=tree.find_nearest(tail);assert fi is not None
   goal=bpy.data.objects.new('ClothBoneGoal_'+name,None);s.collection.objects.link(goal);goal.hide_render=True;goal.empty_display_size=.005;goal.parent=proxy;goal.parent_type='VERTEX_3';goal.parent_vertices=faces[fi];bpy.context.view_layer.update()
   # matrix_world's setter consults the unevaluated parent and cannot see
   # Geometry Nodes output. Calibrate local basis from the evaluated frame.
   dg=bpy.context.evaluated_depsgraph_get();parentframe=goal.evaluated_get(dg).matrix_world.copy();goal.matrix_basis=parentframe.inverted()@Matrix.Translation(tail);bpy.context.view_layer.update()
   error=(goal.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation-tail).length;assert error<5e-6,('Triangle parenting rest offset',name,error)
   goals.append(goal);bindings.append(dict(bone=name,proxy=proxy.name,triangle=list(faces[fi]),tail_to_surface_m=float(distance),rest_target_error_m=error))
 for goal,row in zip(goals,bindings):
  con=arm.pose.bones[row['bone']].constraints.new('DAMPED_TRACK');con.name='ClassicCloth_跟踪代理_保留原蒙皮';con.target=goal;con.track_axis='TRACK_Y';constraints.append(con)
 bpy.context.view_layer.update();initial_error=float(np.max(np.abs(coords(actor)-initial)));assert initial_error<.0001,('Initial tracking interface',initial_error)
 controls=[]
 for frame in [1,151,226,331,376,450]:
  s.frame_set(frame);bpy.context.view_layer.update();actual=coords(actor)
  for con in constraints:con.influence=0.
  bpy.context.view_layer.update();reference=coords(actor)
  for con in constraints:con.influence=1.
  bpy.context.view_layer.update();error=float(np.max(np.abs(actual-reference)));controls.append(dict(frame=frame,rigid_transfer_error_m=error));assert error<.0001,('Rigid head tracking interface',frame,error)
 s.frame_set(1);bpy.context.view_layer.update();status('144_NATIVE_TRACKING_BINDINGS_READY',initial_error_m=initial_error,maximum_rigid_transfer_error_m=max(q['rigid_transfer_error_m'] for q in controls))
 # Reuse the exact previous physical trajectory for the failed seven frames.
 # This tests only the replacement display mapping, without rerunning Cloth.
 cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
    if not dst.exists():shutil.copy2(src,dst)
    md.filepath=str(dst)
 replay=[]
 for j,row in enumerate(prepared['proxies']):
  proxy=bpy.data.objects[row['proxy']]
  for md in proxy.modifiers:md.show_viewport=False;md.show_render=False
  src=Path(a.previous)/'cache'/f'ClassicHair_{j:02d}.pc2';dst=cache/src.name;shutil.copy2(src,dst)
  md=proxy.modifiers.new('OnlyPreviousTrajectory_MappingCheck','MESH_CACHE');md.cache_format='PC2';md.filepath=str(dst);md.play_mode='CUSTOM';md.time_mode='FRAME';md.driver_add('eval_frame').driver.expression='frame-1';replay.append((proxy,md))
 skin=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy');bf=np.load(base/'fullhair_repro_20261030/input_body_aware/body_faces.npy');body=np.load(base/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r');ids=inspection['ids'];edge=inspection['edges'];length=np.linalg.norm(initial[ids[edge[:,0]]]-initial[ids[edge[:,1]]],axis=1);valid=length>.001;rows=[];stop=None
 for frame in range(1,8):
  s.frame_set(frame);bpy.context.view_layer.update();co=coords(actor);bodyerr=float(np.abs(co[skin]-body[(frame-1)*8]).max());assert bodyerr<5e-6
  field=ClosedColliderField(co[skin],bf);distance,_=field(co[ids]);contact=embedded_patch_metrics(co[ids],distance,edge,limit_m=.05);now=np.linalg.norm(co[ids[edge[:,0]]]-co[ids[edge[:,1]]],axis=1);ratio=np.ones(len(length));ratio[valid]=now[valid]/length[valid];extension=now-length;stretched=[]
  for j,chain in enumerate(meta['chains']):
   select=(inspection['chain_labels'][edge[:,0]]==j)&(inspection['chain_labels'][edge[:,1]]==j)&valid
   if np.quantile(ratio[select],.99)>1.5 and extension[select].max()>.02:stretched.append(chain['name'])
  row=dict(frame=frame,maximum_depth_m=contact['maximum_depth_m'],maximum_connected_extent_m=contact['maximum_patch_extent_m'],over_5cm=contact['exceeds_limit'],edge_ratio_p01_p99=np.quantile(ratio[valid],[.01,.99]).tolist(),maximum_body_error_m=bodyerr,stretched_chains=stretched,previous_failed_edge_length_m=float(np.linalg.norm(co[65234]-co[65235])));rows.append(row)
  if contact['exceeds_limit'] or stretched:stop=dict(**row,worst_patch=contact['patches'][0] if contact['patches'] else None);break
 previous_blend=out/'完整角色_发骨跟踪_原缓存复查.blend';s.frame_end=frame;s['FullHairCachePublication']=str(out/'publication.json');(out/'publication.json').write_text(json.dumps(dict(published_through_frame=frame)),'utf8');bpy.ops.wm.save_as_mainfile(filepath=str(previous_blend))
 (out/'previous_cache_check.json').write_text(json.dumps(dict(status='STOPPED_ACTUAL_CONTACT_OR_STRETCH' if stop else 'PREVIOUS_7_FRAME_TRACKING_MAPPING_PASSED',source_trajectory=str(Path(a.previous)),new_physics=False,blend=str(previous_blend),stop=stop,samples=rows),ensure_ascii=False,indent=2),'utf8')
 if stop:status('STOPPED_ON_ACTUAL_PREVIOUS_CACHE_MAPPING',stop=stop);sys.exit(0)
 for proxy,md in replay:
  proxy.modifiers.remove(md)
  for modifier in proxy.modifiers:modifier.show_viewport=True;modifier.show_render=True
  proxy.hide_render=True
 s.frame_end=450;s.frame_set(1);bpy.context.view_layer.update();del s['FullHairCachePublication'];assert np.abs(coords(actor)-initial).max()<.0001
 blend=out/'完整角色_Cloth代理驱动发骨_未物理.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 result=dict(prepared,status='FULL_HEAD_CLOTH_BONE_TRACKING_READY',blend=str(blend),source_surface_preparation=prepared['blend'],bone_tracking_bindings=bindings,rigid_transfer_controls=controls,initial_tracking_error_m=initial_error,display_transfer='Native triangle parenting and Damped Track on original hair bones; original skin weights',surface_deform_active=False,previous_cache_check=str(out/'previous_cache_check.json'),new_physics_started=False,shutdown_forbidden=True)
 (out/'setup.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');status('BONE_TRACKING_READY_FOR_NATIVE_CLOTH',blend=str(blend),bones=len(bindings))
except SystemExit:raise
except BaseException as exc:status('SCRIPT_OR_BINDING_INTERFACE_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
