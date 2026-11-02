"""Repair rod-to-bone joint continuity with stock Damped Track constraints.

Uses the existing native physical trajectory unchanged; no dynamics or
contact correction is performed. Only child-bone translations are removed,
and native tracking aims each bone at the next physical joint target.
"""
import bpy,sys,json,argparse,shutil,numpy as np
from pathlib import Path
from mathutils import Vector,Quaternion
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
r=json.loads((run/'result.json').read_text('utf8'));motion=np.load(run/'native_rod_physics.npz');last=r['frames'][1]
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor)
base=repo.parent/'work/headswap_xl_codex';d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));chains=[c for c in meta['chains'] if c['name'] in ['Sidehair1.L','Sidehair1.R']];names={n for c in chains for n in c['bones']};children={n for c in chains for n in c['bones'][1:]}
restmat={n:(arm.matrix_world@arm.pose.bones[n].matrix).copy() for n in names};resttail={n:arm.matrix_world@arm.pose.bones[n].tail for n in names};indices={n:ci*22+i*3 for ci,c in enumerate(chains) for i,n in enumerate(c['bones'])}
arm.animation_data.action=arm.animation_data.action.copy();arm.animation_data.action.name='NativeHairDynamics_原生追踪_连续骨链'
for layer in arm.animation_data.action.layers:
 for strip in layer.strips:
  for bag in getattr(strip,'channelbags',[]):
   for fc in list(bag.fcurves):
    if any(fc.data_path=='pose.bones['+json.dumps(n)+'].location' for n in children):bag.fcurves.remove(fc)
for name in children:arm.pose.bones[name].location=(0,0,0);arm.pose.bones[name].keyframe_insert('location',frame=1,group=name)
targets={}
for name in names:
 ob=bpy.data.objects.new('NativeRodGoal_'+name,None);s.collection.objects.link(ob);ob.hide_render=True;ob.location=resttail[name];targets[name]=ob
for f in range(1,last+1):
 current=motion['coordinates'][f-1];q=motion['rotations'][f-1];restco=motion['coordinates'][0];q0=motion['rotations'][0];heads={};tails={}
 for name in names:
  i=indices[name];delta=Quaternion(q[i].tolist())@Quaternion(q0[i].tolist()).inverted();heads[name]=Vector(current[i])+delta@(restmat[name].translation-Vector(restco[i]));tails[name]=Vector(current[i])+delta@(resttail[name]-Vector(restco[i]))
 for c in chains:
  for j,name in enumerate(c['bones']):
   targets[name].location=heads[c['bones'][j+1]] if j+1<len(c['bones']) else tails[name];targets[name].keyframe_insert('location',frame=f)
for name in names:
 constraint=arm.pose.bones[name].constraints.new('DAMPED_TRACK');constraint.name='NativeRod_保持连续_追踪下关节';constraint.target=targets[name];constraint.track_axis='TRACK_Y'
s.frame_set(1);bpy.context.view_layer.update();err=float(np.max(np.abs(coords(actor)-initial)));assert err<5e-6,('Tracking changes initial display',err)
exp=base/'fullhair_repro_20261030/input_body_aware';skin=np.load(exp/'skin_ids.npy');faces=np.load(exp/'body_faces.npy');body=np.load(exp/'body.npy',mmap_mode='r');rows=[]
for f in range(1,last+1):
 s.frame_set(f);bpy.context.view_layer.update();co=coords(actor);bodyerr=float(np.max(np.abs(co[skin]-body[(f-1)*8])));assert bodyerr<5e-6
 field=ClosedColliderField(co[skin],faces);distance,_=field(co[d['ids']]);contact=embedded_patch_metrics(co[d['ids']],distance,d['edges'],limit_m=.05)
 gap=max((arm.matrix_world.to_3x3()@(arm.pose.bones[p].tail-arm.pose.bones[ch].head)).length for c in chains for p,ch in zip(c['bones'][:-1],c['bones'][1:]))
 row=dict(frame=f,maximum_depth_m=contact['maximum_depth_m'],maximum_patch_extent_m=contact['maximum_patch_extent_m'],over_5cm=contact['exceeds_limit'],maximum_joint_gap_m=gap,body_error_m=bodyerr);rows.append(row)
 if f%15==1 or f==last:print('NATIVE_CHAIN_TRACKING_CHECK',json.dumps(row),flush=True)
cache=out/'cache';cache.mkdir(exist_ok=True)
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   src=Path(bpy.path.abspath(md.filepath));dst=cache/src.name
   if not dst.exists():shutil.copy2(src,dst)
   md.filepath=str(dst)
blend=out/'完整角色_原生连续骨链_缓存复查.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report=dict(status='NATIVE_TRACKING_INTERFACE_WITHIN_5CM_ON_EXISTING_PHYSICS' if not any(r['over_5cm'] for r in rows) else 'NATIVE_TRACKING_INTERFACE_CONTACT_STILL_EXCEEDS_5CM',source=r['blend'],blend=str(blend),frames=[1,last],samples=rows,new_physics=False,unchanged_native_physics_cache=str(run/'native_rod_physics.npz'),original_weights_edited=False,initial_display_error_m=err,maximum_joint_gap_m=max(r['maximum_joint_gap_m'] for r in rows),maximum_patch_extent_cm=max(r['maximum_patch_extent_m'] for r in rows)*100,maximum_depth_cm=max(r['maximum_depth_m'] for r in rows)*100,over_limit_frames=[r['frame'] for r in rows if r['over_5cm']],shutdown_forbidden=True)
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False),flush=True)
