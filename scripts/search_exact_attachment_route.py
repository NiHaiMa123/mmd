"""Small smooth route family, checked on true subframe skin before baking."""
import json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.root_envelope_feedback import capsule_features
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal,clamp_reachable_goal
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
from animation_contact_tools.closed_collider_field import ClosedColliderField
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';source_dir=root/'left_arm_feedback_refined';out=root/'left_arm_feedback_exact_v2';out.mkdir(exist_ok=True);source=json.loads((source_dir/'source.json').read_text('utf8'))['source'];profile=json.loads((source_dir/'profile.json').read_text('utf8'));envelope=json.loads((source_dir/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');envelope['attachment_points']=initial['coordinates'][initial['pinned']].tolist();count=int(envelope['root_guide_points']);rest=np.asarray(envelope['guide'])[:count];radii=np.asarray(envelope['radii'])[:count];coverage,_=capsule_features(np.asarray(envelope['attachment_points']),rest,radii);envelope['fixed_root_point_coverage_max_gap_m']=float(coverage.max());assert coverage.max()<=1e-6,coverage.max();engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];moving=sorted({i for role in envelope['moving_regions'] for i in parts['ids'][role]});descendants={b.name for b in arm.data.bones if b.name==chain[2] or chain[2] in {p.name for p in b.parent_recursive}};handgroups={g.index for g in mesh.vertex_groups if g.name in descendants};pure=[i for i in parts['ids']['hand.L'] if sum(g.weight for g in mesh.data.vertices[i].groups if g.group in handgroups)>.999];bind=np.asarray(envelope['anchor_bind_matrix']);frames=np.arange(238.,250.001,.25);cache=[];start=time.monotonic();skin_ids,skin_faces,skin_meta=build_exact_skin_topology(mesh,arm,profile);attachments=np.asarray(envelope['attachment_points']);envelope['validation_mode']='exact_attachment'
for f in frames:
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);delta=np.array(arm.matrix_world@arm.pose.bones[envelope['anchor_bone']].matrix)@np.linalg.inv(bind);guide=rest@delta[:3,:3].T+delta[:3,3];s=np.array(arm.matrix_world@bones[0].head);e=np.array(arm.matrix_world@bones[1].head);w=np.array(arm.matrix_world@bones[2].head);cache.append({'frame':float(f),'hand':co[pure],'guide':guide,'shoulder':s,'wrist':w,'length':np.linalg.norm(e-s)+np.linalg.norm(w-e),'lengths':(np.linalg.norm(e-s),np.linalg.norm(w-e)),'base_quaternions':[b.rotation_quaternion.copy() for b in bones],'base_locations':[b.location.copy() for b in bones],'base_scales':[b.scale.copy() for b in bones],'rotation':delta[:3,:3],'attachment':attachments@delta[:3,:3].T+delta[:3,3]})
directions=np.array([(x,y,z) for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1) if x or y or z]+[(2,0,-1),(-2,0,-1),(2,-1,-1),(-2,-1,-1),(1,1,-2),(-1,1,-2)],dtype=float);directions/=np.linalg.norm(directions,axis=1)[:,None]
def weight(f,ramp):
 u=min(1.,max(0.,(f-238)/ramp));v=min(1.,max(0.,(250-f)/ramp));return (u*u*(3-2*u))*(v*v*(3-2*v))
polisher=FrameProjector(mesh,arm,dict(profile,preserve_wrist_orientation=False,clearance_m=.001),parts,[chain],limit_degrees=3);polisher.bones=[bones[2]];polisher.n=3
def projected_offset(row,offset):
 if np.linalg.norm(offset)<1e-12:return np.zeros(3)
 target,clamp=clamp_reachable_goal(row['shoulder'],row['lengths'],row['wrist']+offset);return target-row['wrist']
bpy.context.scene.frame_set(244);bpy.context.view_layer.update();probe=next(r for r in cache if r['frame']==244);field=ClosedColliderField(coords(mesh)[skin_ids],skin_faces);dd,nn=field(probe['attachment']);contact_direction=-nn[np.argmin(dd)];print('EXACT_ATTACHMENT_NORMAL',float(dd.min()),contact_direction.tolist(),flush=True)
trials=[];accepted=None
for amplitude in (.0125,.025,.05,.075,.10,.125):
 configs=[]
 for ramp in (3.,4.,5.):
  weights=np.array([weight(row['frame'],ramp) for row in cache])
  for space in ('HEAD','WORLD'):
   for direction in directions:
    vector=direction*amplitude;worst=float('inf');feasible=True
    for row,w in zip(cache,weights):
     offset=projected_offset(row,w*(row['rotation']@vector if space=='HEAD' else vector))
     gap,_=capsule_features(row['hand']+offset,row['guide'],radii);worst=min(worst,float(gap.min()))
     if gap.min()<-.035:feasible=False;break
    if feasible:configs.append({'vector':vector,'ramp':ramp,'space':space,'minimum_hand_gap':worst,'score':-worst})
 configs.sort(key=lambda c:float(np.linalg.norm(c['vector']/np.linalg.norm(c['vector'])-contact_direction)));print('SMOOTH_ATTACHMENT_PREFILTER',amplitude,len(configs),flush=True)
 for config in configs:
  for swivel in (0.,-.35,.35,-.7,.7):
   bad=None;rows=[]
   for row in sorted(cache,key=lambda r:(abs(r['frame']-244),r['frame'])):
    f=row['frame'];bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();before=row['base_quaternions'];
    for b,q,loc,scale in zip(bones,before,row['base_locations'],row['base_scales']):b.rotation_quaternion=q;b.location=loc;b.scale=scale
    arm.update_tag();bpy.context.view_layer.update();w=weight(f,config['ramp']);detail=apply_two_bone_goal(arm,chain,row['wrist']+projected_offset(row,w*(row['rotation']@config['vector'] if config['space']=='HEAD' else config['vector'])),1.,w*swivel)
    if detail['endpoint_error_m']>.0001:bad={'frame':f,'reason':'reach'};break
    angles=[float(np.degrees(q.rotation_difference(b.rotation_quaternion).angle)) for q,b in zip(before,bones)]
    if max(angles[:2])>75 or angles[2]>120:bad={'frame':f,'reason':'joint_limit'};break
    co=coords(mesh);gap,_=capsule_features(co[moving],row['guide'],radii)
    # The capsule is diagnostic only; true attachment geometry gates acceptance.
    audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=100000)
    polish=np.zeros(3)
    if audit['ordinary_crossings'] or audit['ordinary_contained_samples']:
     polisher.capture();polish,polish_result=polisher.solve(iterations=24);co=coords(mesh);audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=100000);gap,_=capsule_features(co[moving],row['guide'],radii)
    if audit['ordinary_crossings'] or audit['ordinary_contained_samples']:bad={'frame':f,'reason':'body','crossings':audit['ordinary_crossings'],'pairs':[(r['pair'],r['triangle_crossings']) for r in audit['pairs'] if r['triangle_crossings']]};break
    field=ClosedColliderField(co[skin_ids],skin_faces);distance,_=field(row['attachment']);root_gap=float(distance.min())
    if root_gap<.003:bad={'frame':f,'reason':'exact_attachment','gap_m':root_gap};break
    rows.append({'frame':f,'root_proxy_gap_m':float(gap.min()),'exact_attachment_gap_m':root_gap,'angles':angles,'wrist_polish':polish.tolist()})
   trial={'amplitude_m':amplitude,'vector':config['vector'].tolist(),'space':config['space'],'ramp_frames':config['ramp'],'swivel_peak':swivel,'failure':bad};trials.append(trial);print('SMOOTH_ATTACHMENT_TRIAL',json.dumps(trial),flush=True)
   if bad is None:accepted=(config,swivel,rows);break
  if accepted:break
 if accepted:break
result={'source':source,'accepted':False,'trials':trials,'seconds':time.monotonic()-start,'body_motion_candidate_only':True};(out/'search_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
if accepted is None:raise RuntimeError('No smooth attachment route in the sampled family')
config,swivel,rows=accepted;waypoints=[{'frame':float(f),'offset':projected_offset(row,weight(f,config['ramp'])*(row['rotation']@config['vector'] if config['space']=='HEAD' else config['vector'])).tolist(),'swivel':float(weight(f,config['ramp'])*swivel),'wrist_polish':next(r['wrist_polish'] for r in rows if r['frame']==float(f))} for f,row in zip(frames,cache)];route={'status':'SMOOTH_ARM_ROUTE_REQUIRES_BAKE_AND_INDEPENDENT_VALIDATION','waypoints':waypoints,'maximum_requested_offset_m':float(np.linalg.norm(config['vector'])),'maximum_offset_m':max(float(np.linalg.norm(n['offset'])) for n in waypoints),'frames':[238,250],'samples':rows};(out/'planned_route.json').write_text(json.dumps(route,ensure_ascii=False,indent=2),encoding='utf8')
for name,data in [('profile.json',profile),('envelope.json',envelope),('source.json',{'source':source})]:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print('SMOOTH_ATTACHMENT_FOUND',config['vector'].tolist(),config['ramp'],swivel,flush=True)
