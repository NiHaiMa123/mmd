"""Automatic low-dimensional, length-preserving arm detour search.

Parameters are shared by a whole detected contact window, never hand-keyed per
frame. Exact root/skin tests choose amplitude, direction and elbow swivel. Joint
skin correction is deliberately rebaked after the new motion, not reused stale.
"""
from pathlib import Path
prefix=Path(__file__).with_name('solve_full_hair_root_feedback.py').read_text('utf-8-sig').split('for iteration in range(a.iterations):')[0]
exec(prefix)
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal
# The old wrist cache encodes old joint angles and must not constrain a new route.
for modifier in m.modifiers:
 if modifier.name.startswith('Local joint volume'):modifier.show_viewport=False;modifier.show_render=False

side_windows={}
def envelope(frame,side):
 begin,end=side_windows[side];rise=np.clip((frame-begin)/6.,0,1);fall=np.clip((end-frame)/6.,0,1);return float(min(rise*rise*(3-2*rise),fall*fall*(3-2*fall)))

def reset(state):
 f=state['frame'];s.frame_set(int(f),subframe=f%1)
 for b,q in zip(solver.bones,state['base']):b.rotation_quaternion=q
 for b,q in zip(solver.wrists,state['wrist_base']):b.rotation_quaternion=q
 arm.update_tag();bpy.context.view_layer.update()

# Add the deepest automatically found quarter-frame witnesses to the search grid.
extra=sorted(scan['failures'],key=lambda r:r['min_distance_m'])[:20]
for failure in extra:
 f=failure['frame']
 if any(abs(q['frame']-f)<1e-7 for q in states):continue
 s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();mat=np.array([arm.matrix_world@arm.pose.bones[n].matrix for n in anchors]);roots=sum((local[b]@mat[b,:3,:3].T+mat[b,:3,3])*weights[:,b,None] for b in range(len(anchors)));states.append(dict(frame=f,base=[q.copy() for q in solver.base],wrist_base=[q.copy() for q in solver.wrist_base],hand_frames=[q.copy() for q in solver.hand_frames],roots=roots))
for state in states:
 reset(state);state['wrists']=[np.array(arm.matrix_world@arm.pose.bones[chain[2]].head) for chain in profile['control_chains']]

camera=np.array(s.camera.matrix_world.translation);head_origin=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix.translation);forward=camera-head_origin;forward[2]=0;forward/=np.linalg.norm(forward);selected=[None,None];trials=[];started=time.monotonic()
def apply_routes(state,candidates):
 reset(state);details=[]
 for side,candidate in enumerate(candidates):
  if candidate is None:continue
  e=envelope(state['frame'],side)
  if e==0:continue
  chain=profile['control_chains'][side];goal=state['wrists'][side]+np.array(candidate['direction'])*candidate['amplitude_m']*e;detail=apply_two_bone_goal(arm,chain,goal,candidate.get('wrist_preserve',1.),candidate['swivel_rad']*e);details.append(detail)
 return details

def min_gap(co,roots,side):
 limb=limbs[side];limb['points'].assign(limb_points(co,limb).astype(np.float32));limb['mesh'].refit();root_gpu.assign(roots.astype(np.float32));wp.launch(query_details,nroots,inputs=[limb['mesh'].id,root_gpu,distance_gpu,normals_gpu,face_gpu,bary_gpu],device='cuda:0');d=distance_gpu.numpy();fi=face_gpu.numpy();real=fi<limb['topology']['actual_faces'];return float(d[real].min()) if real.any() else 1.

for side in range(2):
 side_name='L' if side==0 else 'R';baseline=[]
 for state in states:
  apply_routes(state,selected);baseline.append(min_gap(coords(m),state['roots'],side))
 active=[state['frame'] for state,gap in zip(states,baseline) if gap<.0015]
 side_windows[side]=(max(first,math.floor(min(active)-6)),min(last,max(active)+6)) if active else (first,last)
 print('AUTOMATIC_SIDE_WINDOW',side_name,side_windows[side],flush=True)
 order=np.argsort(baseline);ordered=[states[k] for k in order];reset(ordered[0]);shoulder=np.array(arm.matrix_world@arm.pose.bones[profile['control_chains'][side][0]].head);lateral=np.array([np.sign(shoulder[0]-head_origin[0]),0,0.]);up=np.array([0.,0.,1.]);directions=[forward,.8*forward+.6*lateral,.8*forward+.6*up,.8*forward-.6*up,.5*forward+.866*lateral]
 directions=[d/np.linalg.norm(d) for d in directions];pool=[]
 for amplitude in [0,.02,.04,.06,.08,.10,.12,.15,.18]:
  for di,direction in enumerate(directions if amplitude else [directions[0]]):
   for swivel in [0,10,-10,20,-20,30,-30]:
    for preserve in [1.,.5,0.]:pool.append(dict(amplitude_m=amplitude,direction=direction.tolist(),direction_index=di,swivel_rad=float(np.radians(swivel)),wrist_preserve=preserve,cost=amplitude+.0003*abs(swivel)+.001*di+.004*(1-preserve)))
 pool.sort(key=lambda q:q['cost']);chosen=None
 for ci,candidate in enumerate(pool):
  candidates=selected.copy();candidates[side]=candidate;minimum=1.;failed_frame=None;clamp=0.
  for state in ordered:
   details=apply_routes(state,candidates);co=coords(m);gap=min_gap(co,state['roots'],side);minimum=min(minimum,gap);clamp=max(clamp,max((d['goal_clamp_m'] for d in details),default=0.))
   if gap<.0015:failed_frame=state['frame'];break
  # Root clearance cannot justify introducing arm/head/torso intersections.
  # Adjacent wrist skinning is separately rebaked and audited after IK.
  if failed_frame is None:
   side_roles={'arm.'+side_name,'hand.'+side_name};route_pairs=[pair for pair in profile['pairs'] if side_roles.intersection(pair) and set(pair)!={'arm.'+side_name,'hand.'+side_name}];route_profile=dict(profile,pairs=route_pairs)
   for state in states:
    apply_routes(state,candidates);body_audit=audit_frame(m,arm,route_profile,parts,hair=False,cap=1)
    if body_audit['ordinary_crossings'] or body_audit['ordinary_contained_samples']:failed_frame=state['frame'];break
  trial=dict(side=side_name,trial=ci,parameters=candidate,minimum_root_gap_m=minimum,failed_frame=failed_frame,max_goal_clamp_m=clamp,elapsed_s=time.monotonic()-started);trials.append(trial)
  if ci%15==0 or failed_frame is None:print('AUTOMATIC_ROUTE_TRIAL',json.dumps(trial),flush=True);(out/'route_progress.json').write_text(json.dumps(trial,indent=2),encoding='utf8')
  if failed_frame is None:chosen=candidate;break
 if chosen is None:
  (out/'route_failed.json').write_text(json.dumps(dict(side=side_name,trials=trials,physics_started=False),indent=2),encoding='utf8');raise RuntimeError('No candidate within configured route pool; do not render as passed')
 selected[side]=chosen;print('AUTOMATIC_ROUTE_SELECTED',side_name,chosen,flush=True)

poses=[];rows=[];sample_frames=sorted(set(np.arange(first,last+.0001,.125).tolist()+[last]))
for k,f in enumerate(sample_frames):
 s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();mat=np.array([arm.matrix_world@arm.pose.bones[n].matrix for n in anchors]);roots=sum((local[b]@mat[b,:3,:3].T+mat[b,:3,3])*weights[:,b,None] for b in range(len(anchors)));state=dict(frame=f,base=[q.copy() for q in solver.base],wrist_base=[q.copy() for q in solver.wrist_base],hand_frames=[q.copy() for q in solver.hand_frames],roots=roots,wrists=[np.array(arm.matrix_world@arm.pose.bones[chain[2]].head) for chain in profile['control_chains']]);apply_routes(state,selected);co=coords(m);minimum=min(min_gap(co,roots,j) for j in range(2));rows.append(dict(frame=f,minimum_limb_root_gap_m=minimum,wrist_offsets_m=[float(np.linalg.norm(np.array(arm.matrix_world@arm.pose.bones[chain[2]].head)-state['wrists'][j])) for j,chain in enumerate(profile['control_chains'])]));bones=[arm.pose.bones[n] for chain in profile['control_chains'] for n in chain];poses.append((f,[b.rotation_quaternion.copy() for b in bones]))
 if k%80==0:print('ROUTE_DENSE',f,minimum,flush=True)
action=bpy.data.actions.new('FullHair_AutomaticIKDetour');action.use_fake_user=True;ad=arm.animation_data;ad.action=action;continuity={}
for f,qs in poses:
 for b,q in zip(bones,qs):
  if b.name in continuity and continuity[b.name].dot(q)<0:q.negate()
  continuity[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=f,group=b.name)
for curve in fcurves(action):
 for key in curve.keyframe_points:key.interpolation='LINEAR'
ad.action=None;strip=add_layer(arm,action,'Full hair / automatic IK contact route','REPLACE',int(first),last);strip.extrapolation='NOTHING';s.frame_start=1;s.frame_end=int(manifest['frames'][1]);s.frame_set(1);candidate=out/'完整角色_自动IK避让_需重建腕部修正.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True);report=dict(status='AUTOMATIC_CONTACT_ROUTE_REQUIRES_WRIST_REBAKE_AND_FINAL_AUDIT',source=manifest['source_blend'],candidate=str(candidate),frames=[first,last],selected=selected,trials=trials,dense_root_samples=rows,minimum_limb_root_gap_m=min(r['minimum_limb_root_gap_m'] for r in rows),protected_windows=profile['protected_windows'],old_joint_cache_disabled=True,source_actions_edited=False,physics_started=False,seconds=time.monotonic()-started)
report['side_windows']={str(k):list(v) for k,v in side_windows.items()};report['body_aware_candidate_search']=True
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('AUTOMATIC_ROUTE_BAKED',report['minimum_limb_root_gap_m'],flush=True)

