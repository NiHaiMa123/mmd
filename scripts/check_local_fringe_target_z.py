"""Check Target Z tracking on three left-fringe bones using immutable caches.

Only rest calibration and stock TRACK_TO constraints are configured.
No simulated point, original skin weight, or per-frame pose key is changed.
"""
import argparse,json,sys,time,struct,shutil,traceback
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);source=Path(a.run);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);started=time.monotonic()
def status(stage,**kw):
 row=dict(stage=stage,elapsed_s=time.monotonic()-started,**kw);(out/'status.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8');print('LOCAL_FRINGE_TARGET_Z',json.dumps(row,ensure_ascii=False),flush=True)
try:
 assert not (out/'result.json').exists(),'Fresh output directory required'
 previous=json.loads((source/'result.json').read_text('utf8'));config=json.loads((source/'setup.json').read_text('utf8'));prepared=json.loads((Path(config['prepared']).parent/'setup.json').read_text('utf8'));last=previous['frames'][1]
 engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=previous['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor)
 selected={'FrontHair5-1.L','FrontHair5-2.L','FrontHair5-3.L'};bindings=[x for x in prepared['bone_tracking_bindings'] if x['bone'] in selected];assert len(bindings)==3
 existing=[c for b in arm.pose.bones if b.name in selected for c in b.constraints if c.name.startswith('ClassicCloth_跟踪代理_')];assert len(existing)==3
 for con in existing:con.influence=0.
 bpy.context.view_layer.update();neutral=coords(actor);assert np.abs(initial-neutral).max()<.0001
 rest={x['bone']:(arm.matrix_world@arm.pose.bones[x['bone']].matrix).to_quaternion() for x in bindings}
 for binding in bindings:
  name=binding['bone'];goal=bpy.data.objects['ClothBoneGoal_'+name]
  # The existing helper's initial world orientation is identity. Append the
  # original bone rest orientation in local basis, preserving goal position.
  goal.matrix_basis=goal.matrix_basis@rest[name].to_matrix().to_4x4()
 for binding in bindings:
  name=binding['bone'];con=arm.pose.bones[name].constraints.new('TRACK_TO');con.name='ClassicCloth_仅左刘海_目标Z跟踪';con.target=bpy.data.objects['ClothBoneGoal_'+name];con.owner_space='WORLD';con.target_space='WORLD';con.track_axis='TRACK_Y';con.up_axis='UP_Z';con.use_target_z=True
 bpy.context.view_layer.update();initial_error=float(np.abs(coords(actor)-neutral).max());assert initial_error<.0001,('Rest orientation calibration',initial_error)
 cache=out/'cache';cache.mkdir(exist_ok=True)
 for ob in bpy.data.objects:
  for md in ob.modifiers:
   if md.type=='MESH_CACHE':
    src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
    if not dst.exists():shutil.copy2(src,dst)
    md.filepath=str(dst)
 base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));exp=base/'fullhair_repro_20261030/input_body_aware';skin=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy');expected=np.load(exp/'body.npy',mmap_mode='r');ids=d['ids'];edge=d['edges'];length=np.linalg.norm(neutral[ids[edge[:,0]]]-neutral[ids[edge[:,1]]],axis=1);valid=length>.001
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for device in prefs.devices:device.use=device.type=='OPTIX'
 s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.use_sequencer=False
 def still(frame):
  folder=out/'keyframes';folder.mkdir(exist_ok=True);s.render.filepath=str(folder/f'f{frame:04d}.png');bpy.ops.render.render(write_still=True)
 def measure(frame):
  s.frame_set(frame);bpy.context.view_layer.update();co=coords(actor);assert np.isfinite(co).all();bodyerr=float(np.abs(co[skin]-expected[(frame-1)*8]).max());assert bodyerr<5e-6
  signed,_=ClosedColliderField(co[skin],bf)(co[ids]);contact=embedded_patch_metrics(co[ids],signed,edge,limit_m=.05);now=np.linalg.norm(co[ids[edge[:,0]]]-co[ids[edge[:,1]]],axis=1);ratio=np.ones(len(length));ratio[valid]=now[valid]/length[valid];stretched=[]
  for j,chain in enumerate(meta['chains']):
   select=(d['chain_labels'][edge[:,0]]==j)&(d['chain_labels'][edge[:,1]]==j)&valid
   if np.quantile(ratio[select],.99)>1.5 and (now-length)[select].max()>.02:stretched.append(dict(chain=chain['name'],p99=float(np.quantile(ratio[select],.99)),maximum_edge_extension_m=float((now-length)[select].max())))
  return dict(frame=frame,maximum_depth_m=contact['maximum_depth_m'],maximum_connected_extent_m=contact['maximum_patch_extent_m'],inside_vertices=contact['inside_vertices'],over_5cm=contact['exceeds_limit'],body_error_m=bodyerr,display_edge_ratio_p01_p99=np.quantile(ratio[valid],[.01,.99]).tolist(),stretched_chains=stretched),contact
 keyrows=[];stop=None
 for frame in [1,7,201,226,last]:
  if frame>last:continue
  row,contact=measure(frame);keyrows.append(row);status('CACHED_KEYFRAME_CHECK',**row)
  if frame in [1,226,last] or row['over_5cm'] or row['stretched_chains']:still(frame)
  if row['over_5cm'] or row['stretched_chains']:
   stop=dict(reason='User 5cm displayed hair contact limit exceeded' if row['over_5cm'] else 'Actual displayed hair locally stretches visibly',worst_patch=contact['patches'][0] if contact['patches'] else None,**row);break
 rows=[]
 if stop is None:
  for frame in range(1,last+1):
   row,contact=measure(frame);rows.append(row)
   if frame%15==1:status('ALL_CACHED_FRAMES_CHECK',**row)
   if row['over_5cm'] or row['stretched_chains']:
    still(frame);stop=dict(reason='User 5cm displayed hair contact limit exceeded' if row['over_5cm'] else 'Actual displayed hair locally stretches visibly',worst_patch=contact['patches'][0] if contact['patches'] else None,**row);break
 checked_to=rows[-1]['frame'] if rows else None;s.frame_end=last;s['FullHairCachePublication']=str(out/'publication.json');(out/'publication.json').write_text(json.dumps(dict(published_through_frame=last,run=str(out))),'utf8');blend=out/'完整角色_仅左刘海目标Z跟踪_缓存复查.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
 result=dict(status='STOPPED_LOCAL_FRINGE_TARGET_Z_CONTACT_OR_STRETCH' if stop else 'LOCAL_FRINGE_TARGET_Z_EXISTING_CACHE_WITHIN_5CM',blend=str(blend),frames=[1,last],stop=stop,samples=rows,keyframe_samples=keyrows,source=previous['blend'],source_run=str(source),geometry_transfer='Native TRACK_TO with target Z on FrontHair5-1.L/2.L/3.L only; remaining 141 bones retain original Damped Track',modified_bones=sorted(selected),other_hair_bindings_preserved=True,initial_display_error_m=initial_error,all_hair_collision_solved=False,new_physics_started=False,original_weights_edited=False,body_motion_edited=False,checked_through_frame=checked_to,shutdown_forbidden=True)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');status(result['status'],blend=str(blend),stop=stop,checked_through_frame=checked_to)
except BaseException as exc:status('SCRIPT_OR_BINDING_INTERFACE_ERROR',error=repr(exc),traceback=traceback.format_exc());raise
