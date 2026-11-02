"""Read actual display motion and strain from already-baked upstream trials."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root);base=repo.parent/'work/headswap_xl_codex'
engine('import_export').ensure_mmd_tools();inspection=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));ids=inspection['ids'];edges=inspection['edges'];labels=inspection['chain_labels'];skin=np.load(base/'fullhair_repro_20261030/input_body_aware/skin_ids.npy');expected=np.load(base/'fullhair_repro_20261030/input_body_aware/body.npy',mmap_mode='r')
legacy=base/'jiggle_physics_20261031/candidate13';bpy.ops.wm.open_mainfile(filepath=str(legacy/'完整角色_Jiggle配置_未烘焙.blend'),load_ui=False,use_scripts=False);s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();initial=coords(actor);head_origin=np.array(arm.matrix_world@arm.pose.bones['頭'].head);tips=[]
for label in range(27):
 selected=ids[labels==label];radii=np.linalg.norm(initial[selected]-head_origin,axis=1);tips.append(selected[radii>=np.quantile(radii,.8)])
rest=np.linalg.norm(initial[ids[edges[:,0]]]-initial[ids[edges[:,1]]],axis=1);valid=rest>.001;chain_edges=[np.flatnonzero((labels[edges[:,0]]==j)&(labels[edges[:,1]]==j)&valid) for j in range(27)];entries=[('baseline',legacy)]+[(n,root/n) for n in ['A_ellipsoids_only','B_smaller_radius','C_shorter_root']];results=[];rear=list(range(7,23))+[25,26]
for name,folder in entries:
 source=json.loads((folder/'bake_report.json').read_text('utf8'))['blend'];bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();assert not s.rigidbody_world or not s.rigidbody_world.enabled
 world=[];heads=[];strain=[];body_errors=[];started=time.monotonic()
 for f in range(1,451):
  s.frame_set(f);bpy.context.view_layer.update();co=coords(actor);assert np.isfinite(co).all(),(name,f,'nonfinite displayed geometry');err=float(np.abs(co[skin]-expected[(f-1)*8]).max());body_errors.append(err);assert err<5e-6,(name,f,'protected skin changed',err)
  world.append(np.array([co[t].mean(0) for t in tips]));heads.append(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix));length=np.linalg.norm(co[ids[edges[:,0]]]-co[ids[edges[:,1]]],axis=1);ratio=np.ones(len(rest));ratio[valid]=length[valid]/rest[valid]
  strained=[dict(chain=meta['chains'][j]['name'],p99=float(np.quantile(ratio[e],.99)),maximum_edge_growth_cm=float((length[e]-rest[e]).max()*100)) for j,e in enumerate(chain_edges) if len(e) and np.quantile(ratio[e],.99)>1.5 and (length[e]-rest[e]).max()>.02]
  if strained:strain.append(dict(frame=f,chains=strained))
  if f%30==0:print('TRIAL_MOTION_REVIEW',name,f,flush=True)
 world=np.array(world);heads=np.array(heads);local=np.einsum('fij,fcj->fci',np.linalg.inv(heads[:,:3,:3]),world-heads[:,None,:3,3]);q=local[300:391];velocity=np.diff(q,axis=0);acceleration=np.diff(q,n=2,axis=0);steps=100*np.linalg.norm(velocity,axis=2);rms=100*np.sqrt(np.mean(np.sum((q-q.mean(0))**2,axis=2),axis=0));pi,pj=np.unravel_index(np.argmax(steps),steps.shape)
 result=dict(name=name,blend=source,body_error_m=max(body_errors),frames=[1,450],analysis_frames=[301,391],largest_tip_step_cm=float(steps[pi,pj]),largest_tip_step_chain=meta['chains'][pj]['name'],largest_tip_step_frames=[301+int(pi),302+int(pi)],rear_tip_rms_cm_median=float(np.median(rms[rear])),rear_tip_acceleration_p95_cm=float(np.quantile(100*np.linalg.norm(acceleration[:,rear],axis=2),.95)),strain_flag_frames=len(strain),strain_flags=strain,per_chain=[dict(chain=c['name'],tip_rms_cm=float(rms[j]),maximum_tip_step_cm=float(steps[:,j].max())) for j,c in enumerate(meta['chains'])],motion_is_not_intrusion_depth=True,metrics_are_diagnostics_not_naturalness_acceptance=True,new_simulation_started=False,elapsed_s=time.monotonic()-started)
 np.savez_compressed(root/(name+'_motion.npz'),frames=np.arange(1,451),tip_world=world,head_world=heads,tip_head_local=local);(root/(name+'_motion.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');results.append(result);print('TRIAL_MOTION_DONE',json.dumps({k:v for k,v in result.items() if k not in ['per_chain','strain_flags']}),flush=True)
(root/'motion_comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
