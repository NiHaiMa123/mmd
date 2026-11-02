"""Read-only coverage/clearance analysis; no solver or parameter changes."""
import bpy,sys,json,numpy as np
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
base=repo.parent/'work/headswap_xl_codex';run=base/'native_solid_contact_20261101/side_rods02_user5cm';current=run/'native_tracking_check';out=current/'coverage_analysis';out.mkdir(exist_ok=True)
report=json.loads((current/'result.json').read_text('utf8'));motion=np.load(run/'native_rod_physics.npz');d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));exp=base/'fullhair_repro_20261030/input_body_aware';skin=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=report['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];rows=[]
for frame in [1,201]:
 s.frame_set(frame);bpy.context.view_layer.update();co=coords(actor);field=ClosedColliderField(co[skin],bf)
 for j,ci in enumerate([23,24]):
  guide=motion['coordinates'][frame-1,j*22:(j+1)*22];points=co[d['ids'][d['chain_labels']==ci]];v=np.diff(guide,axis=0);t=np.clip(np.sum((points[:,None,:]-guide[None,:-1,:])*v[None,:,:],axis=2)/np.maximum((v*v).sum(1),1e-14),0,1);q=guide[None,:-1,:]+t[:,:,None]*v[None,:,:];seg=np.argmin(np.sum((points[:,None,:]-q)**2,axis=2),axis=1);nearest=q[np.arange(len(points)),seg];offset=points-nearest;radial=np.linalg.norm(offset,axis=1)
  required=np.zeros(22);np.maximum.at(required,seg,radial);np.maximum.at(required,seg+1,radial)
  clearance,_=field(guide);available=clearance-.003;hd,_=field(points);inside=hd<-.0001;qd,normal=field(nearest);support=np.maximum(0,-np.einsum('ij,ij->i',offset,normal));needed=np.maximum(0,support-.003)
  dense=np.concatenate([np.linspace(a,b,max(3,int(np.ceil(np.linalg.norm(b-a)/.001))+1)) for a,b in zip(guide[:-1],guide[1:])]);sd,_=field(dense)
  row=dict(frame=frame,chain=meta['chains'][ci]['name'],native_radius_mm=6,collision_margin_mm=3,minimum_guide_center_skin_clearance_mm=float(sd.min()*1000),display_radial_offset_p50_p95_max_mm=(np.quantile(radial,[.5,.95,1])*1000).tolist(),inside_display_vertices=int(inside.sum()),inside_display_radial_p50_p95_max_mm=(np.quantile(radial[inside],[.5,.95,1])*1000).tolist() if inside.any() else [],normal_support_radius_estimate_for_buried_points_p50_p95_max_mm=(np.quantile(needed[inside],[.5,.95,1])*1000).tolist() if inside.any() else [],initial_circle_coverage_conflicts=int((required>available+1e-5).sum()) if frame==1 else None,required_conservative_point_radii_mm=(required*1000).tolist(),available_initial_point_radii_mm=(available*1000).tolist() if frame==1 else None)
  rows.append(row)
result=dict(status='READ_ONLY_COVERAGE_ANALYSIS',rows=rows,interpretation_limits='Conservative circular radius uses nearest polyline projection of actual display vertices. Normal-support estimate is a local linear approximation, not a tested new solve. Static circle conflicts indicate full circular coverage does not fit existing body clearance at those samples.',new_physics=False,parameters_changed=False)
(out/'coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
