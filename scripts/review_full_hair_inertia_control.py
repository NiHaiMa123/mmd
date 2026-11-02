"""Read-only cache, actual mesh, and head-relative motion review of both controls."""
import argparse, json, struct, sys
from pathlib import Path
import bpy, numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
p=argparse.ArgumentParser();p.add_argument('--root',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root)
prepared=json.loads((root/'prepared/setup.json').read_text('utf8'))
inspection=np.load(repo.parent/'work/headswap_xl_codex/standard_proxy_20261031/inspection/inputs.npz')
body_input=root/'prepared/input_body_aware';skin=np.load(body_input/'skin_ids.npy');faces=np.load(body_input/'body_faces.npy');expected=np.load(body_input/'body.npy',mmap_mode='r')
heads=np.load(body_input/'head_matrices.npy');rear=list(range(7,23))+[25,26]
engine('import_export').ensure_mmd_tools();reviews=[]
for name in ['baseline01','soft_rear01']:
 run=root/name;result=json.loads((run/'result.json').read_text('utf8'));last=result['frames'][1];motion=np.load(run/'inertia_tip_motion.npz')
 bpy.ops.wm.open_mainfile(filepath=result['blend'],load_ui=False,use_scripts=False)
 s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature()
 s.frame_set(1);bpy.context.view_layer.update();initial=coords(actor);tips=[];proxy_initial=[]
 for j,row in enumerate(prepared['proxies']):
  selected=inspection['ids'][inspection['chain_labels']==j];root_position=np.array(arm.matrix_world@arm.pose.bones[row['chain']].head);r=np.linalg.norm(initial[selected]-root_position,axis=1);tips.append(selected[r>=np.quantile(r,.8)]);proxy_initial.append(coords(bpy.data.objects[row['proxy']]))
 checks=[]
 for frame in sorted(set([1,last]+[f for f in [16,31,46,61,76,91] if f<=last])):
  s.frame_set(frame);bpy.context.view_layer.update();actual=coords(actor);body_error=float(np.max(np.abs(actual[skin]-expected[(frame-1)*8])))
  actual_tips=np.array([actual[t].mean(0) for t in tips]);tip_error=float(np.max(np.abs(actual_tips-motion['display'][frame-1])))
  field=ClosedColliderField(actual[skin],faces);hair=actual[inspection['ids']];vertex_dist,_=field(hair);centroids=hair[inspection['faces']].mean(1);face_dist,_=field(centroids)
  checks.append(dict(frame=frame,body_error_m=body_error,cache_tip_error_m=tip_error,vertex_depth_m=float(max(0,-vertex_dist.min())),face_centroid_depth_m=float(max(0,-face_dist.min()))))
  assert body_error<5e-6 and tip_error<5e-6,(name,frame,checks[-1])
 cache_headers=[]
 for path in sorted((run/'cache').glob('*.pc2')):
  with path.open('rb') as f:magic,version,points,start,step,samples=struct.unpack('<12siiffi',f.read(32))
  assert magic==b'POINTCACHE2\0' and path.stat().st_size==32+points*samples*12,path
  if path.name.startswith('ClassicHair_'):assert samples==last,path
  cache_headers.append(dict(file=path.name,points=points,samples=samples,start=start,step=step))
 assert len([h for h in cache_headers if h['file'].startswith('ClassicHair_')])==27
 local={}
 for key in ['display','proxy']:
  local[key]=np.einsum('fij,fcj->fci',np.linalg.inv(heads[:last,:3,:3]),motion[key]-heads[:last,None,:3,3])
 def stop_metrics(points,first,last_frame):
  end=min(last,last_frame)
  if end<=first:return None
  q=points[first-1:end]
  return dict(start=first,end=end,path_length_cm=(100*np.linalg.norm(np.diff(q,axis=0),axis=2).sum(0)).tolist(),excursion_cm=(100*np.linalg.norm(q-q[0],axis=2).max(0)).tolist())
 chains=[]
 s.frame_set(last);bpy.context.view_layer.update();actual=coords(actor)
 for j,row in enumerate(prepared['proxies']):
  ob=bpy.data.objects[row['proxy']];edges=np.array([e.vertices[:] for e in ob.data.edges]);q=coords(ob);q0=proxy_initial[j];length=np.linalg.norm(q0[edges[:,0]]-q0[edges[:,1]],axis=1);now=np.linalg.norm(q[edges[:,0]]-q[edges[:,1]],axis=1);valid=length>.001
  delta=motion['display'][:,j]-motion['rigid'][:,j]
  chains.append(dict(chain=row['chain'],changed_in_soft_rear=j in rear,maximum_tip_rigid_deviation_cm=float(100*np.linalg.norm(delta,axis=1).max()),final_tip_vertical_drop_vs_rigid_cm=float(-100*delta[-1,2]),final_proxy_edge_ratio_p99=float(np.quantile(now[valid]/length[valid],.99)),maximum_proxy_edge_extension_m=float((now-length).max())))
 reviews.append(dict(preset=result['preset'],frames=[1,last],status=result['status'],stop=result['stop'],scene_gravity=list(s.gravity),scene_use_gravity=s.use_gravity,actual_mesh_checks=checks,cache_headers=cache_headers,all_27_cache_files_valid=True,first_stop_display=stop_metrics(local['display'],16,31),second_stop_display=stop_metrics(local['display'],46,91),first_stop_proxy=stop_metrics(local['proxy'],16,31),second_stop_proxy=stop_metrics(local['proxy'],46,91),chains=chains,maximum_depth_over_all_recorded_frames_cm=100*max(v['maximum_depth_m'] for v in result['samples']),maximum_actual_mesh_check_depth_cm=100*max(max(v['vertex_depth_m'],v['face_centroid_depth_m']) for v in checks),not_a_production_motion=True))
record=dict(control_only=True,original_production_motion_edited=False,rear_indices=rear,reviews=reviews,interpretation='Post-stop head-relative motion can include settling and collision response; it is not by itself proof of natural oscillation. Inspect full-head rendered motion before accepting a preset.')
(root/'review.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
print('INERTIA_CONTROL_REVIEW',json.dumps([dict(preset=r['preset'],frames=r['frames'],stop=r['stop'],maximum_depth_cm=r['maximum_depth_over_all_recorded_frames_cm']) for r in reviews],ensure_ascii=False),flush=True)
