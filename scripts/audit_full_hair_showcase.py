"""Independent native Blender geometry, cache replay, root and skin audit."""
import argparse,sys,json,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.surface_contact_projection import contact_samples
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--frames');p.add_argument('--first',type=float,default=1);p.add_argument('--last',type=float,default=450);p.add_argument('--step',type=float,default=1);p.add_argument('--full-containment',action='store_true');p.add_argument('--wait-for-publication',action='store_true');p.add_argument('--name',default='native_geometry_audit');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.delivery);pub=json.loads((out/'cache_publication.json').read_text('utf8'));src=Path(pub['input']);run=Path(pub['run']);manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));engine('import_export').ensure_mmd_tools();blend=out/'完整角色_整头连续物理_15秒.blend';bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False);s=bpy.context.scene;m=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];ids=np.load(src/'hair_ids.npy');skin=np.load(src/'skin_ids.npy');hf=np.load(src/'hair_faces.npy');bf=np.load(src/'body_faces.npy');real=np.load(src/'real_body_faces.npy').astype(bool);edges=np.load(src/'hair_edges.npy');hard=np.load(src/'hard_roots.npy');reference=np.load(src/'hair_original.npy');rest=np.load(src/'hair_initial.npy');anchors=np.load(src/'anchors.npy',mmap_mode='r');body=np.load(src/'body.npy',mmap_mode='r');positions=np.load(run/'positions.npy',mmap_mode='r');length=np.linalg.norm(reference[edges[:,0]]-reference[edges[:,1]],axis=1);valid=length>.0005;rows=[];started=time.monotonic();camera=np.array(s.camera.matrix_world);inverse0=np.linalg.inv(anchors[0,-1]);rootlocal=rest[hard]@inverse0[:3,:3].T+inverse0[:3,3];cache_paths=[]
for obj in s.objects:
 for mod in obj.modifiers:
  if mod.type=='MESH_CACHE':
   path=Path(bpy.path.abspath(mod.filepath));assert path.exists(),str(path);cache_paths.append(str(path))
frames=[float(x) for x in a.frames.split(',')] if a.frames else np.arange(a.first,a.last+a.step*.1,a.step)
if a.full_containment:ci,cb=contact_samples(len(ids),edges,hf)
else:
 # With no actual surface crossings, one inside witness per connected hair
 # component detects whole-component containment; GPU queries all vertices.
 from collections import defaultdict
 parent=np.arange(len(ids))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
  return i
 for aa,bb in edges:parent[find(int(aa))]=find(int(bb))
 representatives=sorted({find(i) for i in range(len(ids))})
for f in frames:

 if a.wait_for_publication:
  started_wait=time.monotonic();pub=json.loads((out/'cache_publication.json').read_text('utf8'))
  while f>pub['published_through_frame']:
   status_path=run/'status.json';state=json.loads(status_path.read_text('utf8'));assert state['stage']!='FAILED',state;assert time.monotonic()-started_wait<7200,'Publication timeout';time.sleep(5);pub=json.loads((out/'cache_publication.json').read_text('utf8'))
 assert f<=pub['published_through_frame'];k=round((f-manifest['frames'][0])/manifest['sample_step']);assert abs(manifest['frames'][0]+k*manifest['sample_step']-f)<1e-7
 s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();c=coords(m);x=c[ids];bc=c[skin];skinerr=float(np.abs(bc-body[k]).max());replay=float(np.linalg.norm(x-positions[k],axis=1).max());head=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);rootexpected=rootlocal@head[:3,:3].T+head[:3,3];rooterr=float(np.linalg.norm(x[hard]-rootexpected,axis=1).max());ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/length[valid];ht=BVHTree.FromPolygons(x.tolist(),hf.tolist(),all_triangles=True);bt=BVHTree.FromPolygons(bc.tolist(),bf[real].tolist(),all_triangles=True);pairs=ht.overlap(bt);hx=[Vector(v) for v in x];bv=[Vector(v) for v in bc];realbf=bf[real];hits=[]
 for ha,ba in pairs:
  if crosses([hx[i] for i in hf[ha]],[bv[i] for i in realbf[ba]]):hits.append([ha,ba])
 field=ClosedColliderField(bc,bf);points=np.einsum('si,sij->sj',cb,x[ci]) if a.full_containment else x[representatives];d,_=field(points);inside=int((d<-.0001).sum());camerr=float(np.abs(np.array(s.camera.matrix_world)-camera).max());row=dict(frame=float(f),crossings=len(hits),inside_samples=inside,containment_sample_count=len(points),minimum_sample_distance_m=float(d.min()),min_edge_ratio=float(ratio.min()),max_edge_ratio=float(ratio.max()),root_error_m=rooterr,cache_replay_error_m=replay,skin_export_error_m=skinerr,camera_error=camerr,witness_pairs=hits[:10]);rows.append(row)
 if len(rows)%10==0 or len(frames)<12:print('NATIVE_FULL_HEAD_AUDIT',json.dumps(row),flush=True)
 if hits or inside or replay>3e-6 or rooterr>3e-6 or skinerr>3e-6 or camerr>1e-9 or ratio.min()<.8994 or ratio.max()>1.1006:
  (out/(a.name+'_failure.json')).write_text(json.dumps(dict(rows=rows),indent=2),encoding='utf8');raise RuntimeError(f'Native geometry failure at {f}: {row}')
result=dict(status='NATIVE_BLENDER_FULL_HEAD_SAMPLED_BODY_CONTACT_ROOT_REPLAY_PASS',blend=str(blend),frames=[float(f) for f in frames],samples=len(rows),rows=rows,cache_paths_valid=cache_paths,all_render_hair_vertices=len(ids),all_render_hair_triangles=len(hf),real_skin_triangles=int(real.sum()),closure_triangles_excluded_from_surface_intersection=int((~real).sum()),closure_faces_used_for_inside_sign=True,containment_mode='all vertices, edge midpoints and face centres' if a.full_containment else 'one representative per connected hair component after all surface intersections; solver GPU separately checks every vertex',edge_reference='original initial geometry; source edges longer than 0.5mm; +/-10% with 0.05 percentage-point numerical tolerance',ccd_proven=False,raw_card_self_collision_solved=False,elapsed_s=time.monotonic()-started);(out/(a.name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('NATIVE_AUDIT_PASS',len(rows),flush=True)
