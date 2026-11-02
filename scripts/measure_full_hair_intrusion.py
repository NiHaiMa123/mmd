"""Read-only whole-hair interior audit of the user-identified two stills.

Depth is shortest distance to the body boundary. Embedded patch extent is
reported separately; root/body preservation errors are not contact depth.
No bake, simulation, pose edit or rendering is performed.
"""
import sys,json,time,argparse,numpy as np
from pathlib import Path
import bpy
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
engine('import_export').ensure_mmd_tools()
base=repo.parent/'work/headswap_xl_codex';src=base/'short_sidehair_20261101/revision02_exact_body'
p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--out');p.add_argument('--frames',default='226,376');p.add_argument('--capture-motion',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
out=Path(a.out) if a.out else base/'short_sidehair_20261101/user_75s_125s_measurement';out.mkdir(exist_ok=True,parents=True)
source=a.source or json.loads((src/'setup.json').read_text('utf8'))['blend'];bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False)
s=bpy.context.scene;obj=bpy.data.objects['东雪莲x达妮娅_素体'];export=base/'fullhair_repro_20261030/input_body_aware'
skinids=np.load(export/'skin_ids.npy');bodyfaces=np.load(export/'body_faces.npy')
d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'))
ids=d['ids'];faces=d['faces'];labels=d['chain_labels']
ed=np.sort(np.concatenate([bodyfaces[:,[0,1]],bodyfaces[:,[1,2]],bodyfaces[:,[2,0]]]),axis=1)
_,counts=np.unique(ed,axis=0,return_counts=True)
topology=dict(vertices=len(skinids),faces=len(bodyfaces),boundary_edges=int((counts==1).sum()),nonmanifold_edges=int((counts>2).sum()))
assert topology['boundary_edges']==0 and topology['nonmanifold_edges']==0,topology
def extent(points):
 if not len(points):return dict(aabb_span_cm=[0,0,0],principal_axis_span_cm=0)
 span=np.ptp(points,axis=0);q=points-points.mean(0)
 _,_,v=np.linalg.svd(q,full_matrices=False);projection=q@v[0]
 return dict(aabb_span_cm=(span*100).tolist(),principal_axis_span_cm=float(np.ptp(projection)*100))
rows=[];started=time.monotonic();motion_tips=[];motion_heads=[];tip_ids=[]
if a.capture_motion:
 arm=obj.find_armature();s.frame_set(1);bpy.context.view_layer.update();initial=coords(obj);head_origin=np.array(arm.matrix_world@arm.pose.bones['頭'].head)
 for label in range(len(meta['chains'])):
  selected=ids[labels==label];radii=np.linalg.norm(initial[selected]-head_origin,axis=1);tip_ids.append(selected[radii>=np.quantile(radii,.8)])
 expected_body=np.load(export/'body.npy',mmap_mode='r')
for f in [int(x) for x in a.frames.split(',')]:
 s.frame_set(f);bpy.context.view_layer.update();co=coords(obj);hair=co[ids]
 field=ClosedColliderField(co[skinids],bodyfaces)
 distance,_=field(hair);center=hair[faces].mean(1);fdistance,_=field(center)
 inside=distance<-.0001;finside=fdistance<-.0001
 chains=[]
 for i,c in enumerate(meta['chains']):
  mask=labels==i;buried=inside&mask
  if not buried.any():continue
  chains.append(dict(chain=c['name'],display_vertices=int(mask.sum()),inside_vertices=int(buried.sum()),maximum_inward_depth_cm=float(-distance[buried].min()*100),embedded_display_patch_extent=extent(hair[buried])))
 chains.sort(key=lambda c:c['maximum_inward_depth_cm'],reverse=True)
 row=dict(original_seconds=(f-1)/30,frame=f,display_hair_vertices=len(hair),inside_display_vertices=int(inside.sum()),inside_display_triangle_centroids=int(finside.sum()),maximum_vertex_inward_depth_cm=float(max(0,-distance.min())*100),maximum_face_centroid_inward_depth_cm=float(max(0,-fdistance.min())*100),all_embedded_hair_extent=extent(hair[inside]),chains=chains,body_world_aabb_m=[co[skinids].min(0).tolist(),co[skinids].max(0).tolist()])
 if a.capture_motion:
  error=float(np.abs(co[skinids]-expected_body[(f-1)*8]).max());assert error<5e-6,('Body differs from existing repaired motion',f,error)
  row['body_error_m']=error;motion_tips.append(np.array([co[vi].mean(0) for vi in tip_ids]));motion_heads.append(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix))
 rows.append(row);np.savez_compressed(out/f'frame_{f}_signed_distances.npz',hair_ids=ids,vertex_signed_distance_m=distance,face_centroid_signed_distance_m=fdistance)
 progress=dict(frame=f,samples=len(rows),maximum_depth_cm_so_far=max(max(q['maximum_vertex_inward_depth_cm'],q['maximum_face_centroid_inward_depth_cm']) for q in rows),over_5cm_so_far=sum(max(q['maximum_vertex_inward_depth_cm'],q['maximum_face_centroid_inward_depth_cm'])>5 for q in rows),elapsed_s=time.monotonic()-started)
 tmp=out/'progress.tmp.json';tmp.write_text(json.dumps(progress,indent=2),'utf8');tmp.replace(out/'progress.json')
 print('INTRUSION_MEASURED',json.dumps(row,ensure_ascii=False),flush=True)
report=dict(source=source,world_coordinate_unit='metre (existing scene/export convention; body bounding box supplied for scale check)',scene_unit_scale_length=s.unit_settings.scale_length,body_topology=topology,method='Closed body connected-component union; three-direction ray parity per point; nearest body-boundary distance; all actual display hair vertices and triangle centroids tested',inside_threshold_m=.0001,frames=rows,limitations='Discrete frames; vertex/face-centroid sampling; raw-body closing faces complete body topology; not continuous collision detection or exact maximum over every face interior. Patch principal-axis extent is not penetration depth.',simulation_started=False,render_started=False,elapsed_s=time.monotonic()-started)
(out/'intrusion_measurement.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
if a.capture_motion:np.savez_compressed(out/'head_relative_motion.npz',frames=np.array([r['frame'] for r in rows]),tip_world=np.asarray(motion_tips),head_world=np.asarray(motion_heads),chain_names=np.array([c['name'] for c in meta['chains']]))
print('INTRUSION_MEASUREMENT_COMPLETE',flush=True)
