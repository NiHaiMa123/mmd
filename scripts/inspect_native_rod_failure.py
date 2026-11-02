"""Compare baked physical centreline contact with final visible hair contact."""
import bpy,sys,json,argparse,numpy as np
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.closed_collider_field import ClosedColliderField
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
report=json.loads((run/'result.json').read_text('utf8'));f=report['frames'][1];motion=np.load(run/'native_rod_physics.npz')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=report['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;s.frame_set(f);bpy.context.view_layer.update()
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();co=coords(actor);base=repo.parent/'work/headswap_xl_codex';exp=base/'fullhair_repro_20261030/input_body_aware'
skinids=np.load(exp/'skin_ids.npy');bf=np.load(exp/'body_faces.npy');field=ClosedColliderField(co[skinids],bf)
d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');meta=json.loads((base/'standard_proxy_20261031/inspection/inputs.json').read_text('utf8'));selected=[i for i,c in enumerate(meta['chains']) if c['name'].startswith('Sidehair1.')]
cursor=0;rows=[];guide=motion['coordinates'][-1]
for ci,n in zip(selected,motion['curve_point_counts']):
 n=int(n);points=guide[cursor:cursor+n];samples=[]
 for start,end in zip(points[:-1],points[1:]):samples.extend(np.linspace(start,end,max(2,int(np.ceil(np.linalg.norm(end-start)/.001))+1)))
 samples=np.array(samples);dist,_=field(samples);ids=d['ids'][d['chain_labels']==ci];hd,_=field(co[ids]);buried=co[ids][hd<-.0001]
 joints=[];c=meta['chains'][ci]
 for parent,child in zip(c['bones'][:-1],c['bones'][1:]):joints.append(dict(parent=parent,child=child,gap_m=float((arm.matrix_world.to_3x3()@(arm.pose.bones[parent].tail-arm.pose.bones[child].head)).length)))
 span=float(np.linalg.norm(np.ptp(buried,axis=0))) if len(buried) else 0
 rows.append(dict(chain=c['name'],physical_guide_minimum_signed_body_clearance_m=float(dist.min()),physical_guide_radius_m=.006,collider_margin_m=.003,physical_guide_interior_samples=int((dist<0).sum()),display_inside_vertices=int((hd<-.0001).sum()),display_maximum_depth_m=float(max(0,-hd.min())),display_interior_patch_bbox_diagonal_m=span,maximum_bone_joint_gap_m=max(j['gap_m'] for j in joints),bone_joints=joints))
 cursor+=n
decision=dict(frame=f,original_seconds=(f-1)/30,rows=rows,conclusion='CENTRELINES_CLEAR_BUT_DISPLAY_HAIR_INTERSECTS' if all(r['physical_guide_minimum_signed_body_clearance_m']>0 for r in rows) and any(r['display_inside_vertices'] for r in rows) else 'CHECK_GUIDE_AND_DISPLAY_CONTACT_SEPARATELY',limits='Guide clearance sampled approximately every 1mm. Patch bounding-box diagonal is an extent measure, not penetration depth.',simulation_started=False,new_physics_or_tuning=False,source=report['blend'])
(run/'failure_diagnosis.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),'utf8');print(json.dumps(decision,ensure_ascii=False),flush=True)
publication=dict(published_through_frame=f,run=str(run));(run/'publication.json').write_text(json.dumps(publication),'utf8');s['FullHairCachePublication']=str(run/'publication.json')
bpy.ops.wm.save_as_mainfile(filepath=str(run/'完整角色_失败现场_仅1至7秒.blend'))
