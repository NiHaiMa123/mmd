"""Case wrapper: finite-width PBD corrective, frozen source body and hard roots."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.skin_collision_cage import build_skin_cage
from animation_contact_tools.strand_binding import bind_vertices
from animation_contact_tools.surface_contact_projection import project_surface,edge_colours,contact_samples
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--exact-skin-field',action='store_true');p.add_argument('--out',required=True);p.add_argument('--first',type=float,default=334);p.add_argument('--last',type=float,default=362);p.add_argument('--iterations',type=int,default=160);p.add_argument('--margin',type=float,default=.006);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise ValueError('Use a new output directory')
base=json.loads((run/'report.json').read_text('utf8'));motion=np.load(run/'bundle_motion.npz');ids=motion['ids'];lookup={int(v):i for i,v in enumerate(ids)};selected=set(lookup);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=base['source'],load_ui=False,use_scripts=False);rig_profile_path=Path(base.get('rig_profile',str(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track/rig_profile.json')));profile=json.loads(rig_profile_path.read_text('utf8'));anchor_bone=base.get('anchor_bone','頭');profile['pairs']=[];mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);faces=[];polys=[]
for role in ('hair_root','hair_mobile'):
 for face,poly in zip(parts['faces'][role],parts['source_faces'][role]):
  if all(i in selected for i in face):faces.append(face);polys.append(poly)
 for key in ('faces','ids','source_faces','samples','closed'):parts[key].pop(role,None)
parts['faces']['hair_mobile']=faces;parts['source_faces']['hair_mobile']=polys;parts['ids']['hair_mobile']=ids.tolist();parts['samples']['hair_mobile']=ids[::8].tolist();parts['closed']['hair_mobile']=False
edges=np.array([(lookup[e.vertices[0]],lookup[e.vertices[1]]) for e in mesh.data.edges if all(v in selected for v in e.vertices)]);triangles=np.array([[lookup[v] for v in f] for f in faces]);rest=motion['rest_coordinates'];binding=bind_vertices(rest,motion['rest_guide'],np.array([1.,0,0]) if abs((motion['rest_guide'][1]-motion['rest_guide'][0])[0])<.9*np.linalg.norm(motion['rest_guide'][1]-motion['rest_guide'][0]) else np.array([0.,1,0]));pinned=np.load(run/'initial_projection.npz')['pinned'] if (run/'initial_projection.npz').exists() else binding['segment']<=1
scene=bpy.context.scene;scene.frame_set(base['frames'][0]);bpy.context.view_layer.update();anchor0=np.array(arm.matrix_world@arm.pose.bones[anchor_bone].matrix);anchors=np.asarray(motion['head_deltas'])@anchor0;inverse=np.linalg.inv(anchors);local=np.einsum('fij,fvj->fvi',inverse[:,:3,:3],motion['coordinates'])+inverse[:,None,:3,3]
if a.exact_skin_field:skin_ids,cagefaces,cage_metadata=build_exact_skin_topology(mesh,arm,profile);cage=None
else:cage,cage_metadata=build_skin_cage(mesh,arm,profile,voxel_size=.003,binding_pose='REST');cagefaces=[tuple(p.vertices) for p in cage.data.polygons]
colours=edge_colours(edges);samples=contact_samples(len(ids),edges,triangles);positions=[];targets=[];matrices=[];rows=[];previous=np.zeros((len(ids),3));previous_shape=None;start=time.monotonic()
for f in np.arange(a.first,a.last+.001,.25):
 scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);head=np.array(arm.matrix_world@arm.pose.bones[anchor_bone].matrix);index=int(f-base['frames'][0]);u=f-int(f);target_local=local[index]*(1-u)+local[min(index+1,len(local)-1)]*u;target=target_local@head[:3,:3].T+head[:3,3];distance=ClosedColliderField(co[skin_ids] if a.exact_skin_field else coords(cage),cagefaces)
 fade=min(1.,max(0.,(f-a.first)/4) if a.first>base['frames'][0] else 1.,max(0.,(a.last-f)/4) if a.last<base['frames'][1] else 1.);fade=fade*fade*(3-2*fade)
 if fade==0:result=target.copy();detail={'pinned_error_m':0.,'max_correction_m':0.}
 else:result,detail=project_surface(target,rest,edges,triangles,pinned,distance,initial=target+(previous*.98)@head[:3,:3].T,margin=a.margin,max_displacement=.06*fade,iterations=a.iterations,target_strength=.002,colours=colours,samples=samples,previous_positions=None if previous_shape is None else previous_shape@head[:3,:3].T+head[:3,3])
 previous=(result-target)@np.linalg.inv(head[:3,:3]).T;previous_shape=(result-head[:3,3])@np.linalg.inv(head[:3,:3]).T;actual=co.copy();actual[ids]=result;audit=audit_frame(mesh,arm,profile,parts,hair=True,cap=1000000,coordinates_m=actual);rows.append({'frame':float(f),'crossings':audit['ordinary_crossings'],**detail,'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in audit['pairs'] if r['triangle_crossings']]});positions.append(result.astype(np.float32));targets.append(target.astype(np.float32));matrices.append(head)
 if int(round((f-a.first)*4))%8==0:
  print('SURFACE_WINDOW',json.dumps(rows[-1]),flush=True);(out/'progress.json').write_text(json.dumps({'last_frame':float(f),'samples':rows}),encoding='utf8')
np.savez_compressed(out/'surface_motion.npz',coordinates=positions,target=targets,ids=ids,anchor_matrices=matrices,pinned=pinned,rest_coordinates=rest,edges=edges,triangles=triangles)
report={'status':'FINITE_WIDTH_SURFACE_CORRECTIVE_REQUIRES_VALIDATION','accepted':False,'source_run':str(run),'source':base['source'],'frames':[a.first,a.last],'step_frames':.25,'samples':rows,'failed_collision_samples':sum(r['crossings']>0 for r in rows),'max_correction_m':max(r['max_correction_m'] for r in rows),'root_pin_count':int(pinned.sum()),'body_animation_modified':False,'cage':cage_metadata,'seconds':time.monotonic()-start,'full_model_solved':False,'ccd_proven':False}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('SURFACE_WINDOW_COMPLETE',json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
