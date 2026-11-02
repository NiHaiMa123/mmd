"""Bounded B-spline arm feedback against every corrected true hair root.

Uses exact evaluated skin derivatives and GPU closest-surface queries. Protected
windows are excluded, and no source Action or mesh weight is edited.
"""
import argparse,json,sys,time,math
from pathlib import Path
import bpy,bmesh,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions,audit_frame
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.root_envelope_feedback import cubic_basis
from animation_contact_tools.hair_track import add_layer
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--iterations',type=int,default=16);p.add_argument('--step',type=float,default=.5);p.add_argument('--scan');p.add_argument('--window-start',type=float);p.add_argument('--window-end',type=float);p.add_argument('--source-override');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.input);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
if (out/'report.json').exists():raise ValueError('Use fresh feedback output')
manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));scan=json.loads(Path(a.scan or src.parent/'root_scan/root_scan.json').read_text('utf8'));bad=[r['frame'] for r in scan['failures']];first=a.window_start if a.window_start is not None else math.floor(min(bad)-6);last=a.window_end if a.window_end is not None else max(bad)+6
if a.source_override:manifest['source_blend']=a.source_override
for window in profile['protected_windows']:
 if first<window['start']<=last:last=window['start']-.25
assert not any(first<=w['end'] and last>=w['start'] for w in profile['protected_windows'])
width=3.;centres=np.linspace(first+2*width,last-2*width,max(2,math.ceil((last-first-4*width)/3)+1));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=manifest['source_blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(m,arm,profile);bp=dict(profile,preserve_wrist_orientation=True);solver=FrameProjector(m,arm,bp,parts,profile['control_chains'],limit_degrees=30)
# Import only after Blender's own NumPy has loaded.
sys.path.insert(0,str(ROOT/'tools/contact_stack/venv/Lib/site-packages'));sys.path.insert(0,str(ROOT/'tools/contact_stack'));import warp as wp
from mmd_hair_dynamics.gpu_surface import query_details
initial=np.load(src/'hair_initial.npy');hard=np.load(src/'hard_roots.npy');weights=np.load(src/'anchor_weights.npy')[hard];weights/=weights.sum(1)[:,None];anchor0=np.load(src/'anchors.npy',mmap_mode='r')[0];inv=np.linalg.inv(anchor0);local=np.einsum('bij,vj->bvi',inv[:,:3,:3],initial[hard])+inv[:,None,:3,3];anchors=manifest['anchor_bones'];nroots=int(hard.sum());limbs=[]
previous=arm.data.pose_position;arm.data.pose_position='REST';bpy.context.view_layer.update();rest=coords(m)
from mmd_hair_dynamics.mesh_regions import close_patch_with_virtual_centres
full_skin=np.load(src/'skin_ids.npy');full_faces=np.load(src/'body_faces.npy');face_roles=np.load(src/'body_face_role.npy');role_names=json.loads((src/'body_role_names.json').read_text('utf8'))
def limb_points(co,limb):
 base=co[limb['ids']];return np.vstack([base]+[base[loop].mean(0,keepdims=True) for loop in limb['loops']]) if limb['loops'] else base
for side in ['L','R']:
 selected=np.isin(face_roles,[role_names.index('arm.'+side),role_names.index('hand.'+side)]);skin,faces,loops,fan_meta=close_patch_with_virtual_centres(full_skin[full_faces[selected]]);limb=dict(side=side,ids=skin,faces=faces,loops=loops,topology=fan_meta);points=wp.array(limb_points(rest,limb).astype(np.float32),dtype=wp.vec3,device='cuda:0');mesh=wp.Mesh(points=points,indices=wp.array(faces.ravel(),dtype=int,device='cuda:0'),support_winding_number=True);limb.update(points=points,mesh=mesh);limbs.append(limb);print('LIMB_CLOSURE',side,fan_meta,flush=True)
arm.data.pose_position=previous;bpy.context.view_layer.update();root_gpu=wp.empty(nroots,dtype=wp.vec3,device='cuda:0');distance_gpu=wp.empty(nroots,dtype=float,device='cuda:0');normals_gpu=wp.empty(nroots,dtype=wp.vec3,device='cuda:0');face_gpu=wp.empty(nroots,dtype=int,device='cuda:0');bary_gpu=wp.empty(nroots,dtype=wp.vec3,device='cuda:0')
frames=sorted(set(np.arange(first,last+.0001,a.step).tolist()+[last]));states=[]
for f in frames:
 s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();mat=np.array([arm.matrix_world@arm.pose.bones[n].matrix for n in anchors]);roots=sum((local[b]@mat[b,:3,:3].T+mat[b,:3,3])*weights[:,b,None] for b in range(len(anchors)));states.append(dict(frame=f,base=[q.copy() for q in solver.base],wrist_base=[q.copy() for q in solver.wrist_base],hand_frames=[q.copy() for q in solver.hand_frames],basis=cubic_basis(f,centres,width),roots=roots,clearance=.0005+.002*min(1.,max(0.,min(f-first,last-f)/3.))))
coeff=np.zeros((len(centres),solver.n));history=[];clearance=.0025;start=time.monotonic()
def activate(state,c):
 f=state['frame'];s.frame_set(int(f),subframe=f%1);solver.base=state['base'];solver.wrist_base=state['wrist_base'];solver.hand_frames=state['hand_frames'];solver.apply(state['basis']@c);return coords(m)
def contacts(co,roots):
 root_gpu.assign(roots.astype(np.float32));sets=[];minimum=1.
 for limb in limbs:
  limb['points'].assign(limb_points(co,limb).astype(np.float32));limb['mesh'].refit();wp.launch(query_details,nroots,inputs=[limb['mesh'].id,root_gpu,distance_gpu,normals_gpu,face_gpu,bary_gpu],device='cuda:0');distance=distance_gpu.numpy();all_faces=face_gpu.numpy();real=all_faces<limb['topology']['actual_faces'];minimum=min(minimum,float(distance[real].min()) if real.any() else 1.);active=np.flatnonzero((distance<clearance+.001)&real)
  if not len(active):continue
  # Keep the worst contact in each 4mm cell, never exempting the other roots from validation.
  order=active[np.argsort(distance[active])];keys=np.rint(roots[order]/.004).astype(np.int64);_,keep=np.unique(keys,axis=0,return_index=True);active=order[np.sort(keep)][:350];fi=face_gpu.numpy()[active];normal=normals_gpu.numpy()[active];bary=bary_gpu.numpy()[active];triangles=limb['faces'][fi];surface=np.einsum('si,sij->sj',bary,limb_points(co,limb)[triangles]);sets.append(dict(distance=distance[active].astype(float),normal=normal.astype(float),weights=bary.astype(float),triangles=triangles,surface=surface,limb=limb))
 return sets,minimum
for iteration in range(a.iterations):
 blocks=[];rhs=[];cases=[];worst=1.;body_fail=0
 for state in states:
  co=activate(state,coeff);sets,minimum=contacts(co,state['roots']);worst=min(worst,minimum);audit=audit_frame(m,arm,bp,parts,hair=False,cap=1000,return_witness_pairs=True);cs=solver.constraints(audit,co);body_fail+=int(bool(cs));nroot=sum(len(q['distance']) for q in sets)
  if not nroot and not cs:continue
  gaps=np.concatenate([q['distance'] for q in sets]+([np.array([c[-1] for c in cs])] if cs else []));normal_body=np.asarray([c[-2] for c in cs]);body_base=solver.features(co,cs) if cs else np.empty((0,3));J=np.zeros((len(gaps),solver.n));x=state['basis']@coeff
  for j in range(solver.n):
   pert=x.copy();pert[j]+=.001;solver.apply(pert);nc=coords(m);offset=0
   for q in sets:
    surface=np.einsum('si,sij->sj',q['weights'],limb_points(nc,q['limb'])[q['triangles']]);n=len(surface);J[offset:offset+n,j]=-np.einsum('ij,ij->i',surface-q['surface'],q['normal'])/.001;offset+=n
   if cs:J[nroot:,j]=np.einsum('ij,ij->i',solver.features(nc,cs)-body_base,normal_body)/.001
  solver.apply(x);rowweight=np.r_[np.ones(nroot),np.full(len(cs),4.)];blocks.append(np.hstack([J*v for v in state['basis']])*rowweight[:,None]);rhs.append((state['clearance']-gaps)*rowweight);cases.append((state,sets,cs,body_base,normal_body,gaps,rowweight))
 row=dict(iteration=iteration,min_limb_root_distance_m=worst,body_contact_samples=body_fail,active_frames=len(cases),elapsed_s=time.monotonic()-start);history.append(row);(out/'progress.json').write_text(json.dumps(row,indent=2),encoding='utf8');print('GPU_ROOT_FEEDBACK',json.dumps(row),flush=True)
 np.save(out/'coefficients.npy',coeff)
 if not cases or (worst>=.0005 and not body_fail):break
 J=np.vstack(blocks);b=np.concatenate(rhs);regularization=.00003;step=np.linalg.solve(J.T@J+np.eye(J.shape[1])*regularization,J.T@b-regularization*coeff.ravel()).reshape(coeff.shape);largest=max(np.linalg.norm(r[j:j+3]) for r in step for j in range(0,solver.n,3))
 for row_step in step:
  for control in range(0,solver.n,3):
   norm=np.linalg.norm(row_step[control:control+3])
   if norm>np.radians(2):row_step[control:control+3]*=np.radians(2)/norm
 old=float(np.maximum(b,0)@np.maximum(b,0));accepted=False
 for factor in [1.,.5,.25,.1]:
  candidate=np.array([solver.bounded(r) for r in coeff+factor*step]);score=0.
  for state,sets,cs,body_base,normal_body,gaps,rowweight in cases:
   nc=activate(state,candidate);change=[]
   for q in sets:change.extend((-np.einsum('ij,ij->i',np.einsum('si,sij->sj',q['weights'],limb_points(nc,q['limb'])[q['triangles']])-q['surface'],q['normal'])).tolist())
   if cs:change.extend(np.einsum('ij,ij->i',solver.features(nc,cs)-body_base,normal_body).tolist())
   deficit=np.maximum(state['clearance']-gaps-np.array(change),0)*rowweight;score+=float(deficit@deficit)
  if score<old-1e-12:coeff=candidate;np.save(out/'coefficients.npy',coeff);accepted=True;break
 if not accepted:print('FEEDBACK_LINE_SEARCH_STALLED',flush=True);break
poses=[]
for state in states:
 activate(state,coeff);poses.append((state['frame'],[b.rotation_quaternion.copy() for b in solver.bones+solver.wrists]))
action=bpy.data.actions.new('FullHair_RootAvoidance_Absolute');action.use_fake_user=True;ad=arm.animation_data;ad.action=action
for f,qs in poses:
 for b,q in zip(solver.bones+solver.wrists,qs):b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=f,group=b.name)
for curve in fcurves(action):
 for key in curve.keyframe_points:key.interpolation='LINEAR'
ad.action=None;strip=add_layer(arm,action,'Full hair roots / automatic smooth arm avoidance','REPLACE',int(first),last);strip.extrapolation='NOTHING';s.frame_start=1;s.frame_end=450;s.frame_set(1);candidate=out/'完整角色_自动发根绕行_待复查.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True)
result=dict(status='AUTOMATIC_ROOT_FEEDBACK_REQUIRES_DENSE_REVIEW',source=manifest['source_blend'],candidate=str(candidate),frames=[first,last],centres=centres.tolist(),width=width,coefficients=coeff.tolist(),history=history,protected_windows=profile['protected_windows'],source_actions_edited=False,actual_max_coefficient_degrees=float(np.degrees(np.linalg.norm(coeff.reshape(-1,3),axis=1).max())),algorithm='GPU nearest limb surface + evaluated-skin finite Jacobian + shared cubic B-spline rotations, wrist orientation compensation',seconds=time.monotonic()-start)
(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('ROOT_FEEDBACK_SAVED',flush=True)



