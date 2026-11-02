"""Dense target-shape audit and large views of the corrected sleeve interval."""
import sys,json,argparse,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--no-render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);ie=engine('import_export');ie.ensure_mmd_tools();out=Path(a.fit).resolve();review=out/'sleeve_review';review.mkdir(exist_ok=True);projected=(out/'sleeve_shape_repair.json').exists();result={'scope':'All 450 video frames, including continuous 12–14 second interval; anatomical L/R','frames':{},'summary':{}};old_positions={};side_ids={};edges={};base_lengths={};triangles={};base_areas={};skirt_ids=None;original_hashes={}
def digest(obj):
 h=hashlib.sha256();data=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',data);h.update(data.tobytes())
 if obj.data.shape_keys:
  for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',data);h.update(data.tobytes())
 return h.hexdigest()
def coords(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();co=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',co);ev.to_mesh_clear();return co.reshape(-1,3)
for label,folder in [('before',ROOT/'outputs/cynical_cloth15/chest_hd'),('after',out)]:
 bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;proxy=bpy.data.objects['ClothSimulationSurface'];target=bpy.data.objects['ClothShapePreservingTarget'];mesh=proxy.data;base=np.array([v.co[:] for v in mesh.vertices]);visibility={o:o.hide_viewport for o in ie.model_meshes() if o.name!='达妮娅_mesh'}
 for o in visibility:o.hide_viewport=True
 if label=='before':original_hashes={o.name:digest(o) for o in ie.model_meshes()}
 if not side_ids:
  all_sleeves=set()
  for side in ('L','R'):
   group=proxy.vertex_groups['腕.'+side].index;ids={v.index for v in mesh.vertices if any(g.group==group and g.weight>.5 for g in v.groups)};side_ids[side]=sorted(ids);all_sleeves|=ids;edges[side]=np.array([tuple(e.vertices) for e in mesh.edges if all(i in ids for i in e.vertices)]);base_lengths[side]=np.linalg.norm(base[edges[side][:,0]]-base[edges[side][:,1]],axis=1);triangles[side]=np.array([tuple(f.vertices) for f in mesh.polygons if all(i in ids for i in f.vertices)]);t=triangles[side];base_areas[side]=np.linalg.norm(np.cross(base[t[:,1]]-base[t[:,0]],base[t[:,2]]-base[t[:,0]]),axis=1)
  skirt_ids=sorted(set(range(len(mesh.vertices)))-all_sleeves)
 if label=='after':
  if projected:
   cache_points=np.fromfile(out/'StableSleeveShapes.pc2',dtype='<f4',offset=32).reshape(496,len(mesh.vertices),3);scene.frame_set(496);result['new_cache_random_seek_error_m']=float(np.abs(coords(target)-cache_points[-1]).max());assert result['new_cache_random_seek_error_m']<1e-6
  else:
   new=bpy.data.objects['StableSleeveSimulationSurface'];sim=next(m for m in new.modifiers if m.type=='CLOTH');assert sim.point_cache.is_baked;scene.frame_set(496);positions=coords(new);expected=json.loads((out/'sleeve_simulation_report.json').read_text(encoding='utf-8'))['frames']['496']['bounds'];result['new_cache_random_seek_error_m']=float(np.abs(np.array([positions.min(axis=0),positions.max(axis=0)])-np.array(expected)).max());assert result['new_cache_random_seek_error_m']<1e-5
   ref=bpy.data.objects['ClothKinematicReference'];mapping=np.array([d.value for d in ref.data.attributes['StableSleeveIndex'].data])
  max_solver_error=0.;max_skirt_error=0.
 rows={};previous=None;velocities=[]
 for frame in range(47,497):
  scene.frame_set(frame);co=coords(target);row={}
  if label=='before':old_positions[frame]=co.copy()
  else:
   max_skirt_error=max(max_skirt_error,float(np.abs(co[skirt_ids]-old_positions[frame][skirt_ids]).max()));ids=side_ids['L']+side_ids['R']
   if projected:max_solver_error=max(max_solver_error,float(np.abs(co-cache_points[frame-1]).max()))
   else:
    raw=coords(new);max_solver_error=max(max_solver_error,float(np.abs(co[ids]-raw[mapping[ids]]).max()))
  for side,ids in side_ids.items():
   e=edges[side];ratios=np.linalg.norm(co[e[:,0]]-co[e[:,1]],axis=1)/np.maximum(base_lengths[side],1e-8);t=triangles[side];areas=np.linalg.norm(np.cross(co[t[:,1]]-co[t[:,0]],co[t[:,2]]-co[t[:,0]]),axis=1)/np.maximum(base_areas[side],1e-10);row[side]={'edge_ratio_min':float(ratios.min()),'edge_ratio_p01':float(np.quantile(ratios,.01)),'edge_ratio_p99':float(np.quantile(ratios,.99)),'edge_ratio_max':float(ratios.max()),'area_ratio_p01':float(np.quantile(areas,.01))}
  if previous is not None:velocities.append({'frame':frame,'max_vertex_step_m':float(np.linalg.norm(co-previous,axis=1).max())})
  previous=co;rows[str(frame)]=row
  if frame%100==0:print('SLEEVE_DENSE_AUDIT',label,frame,flush=True)
 result['frames'][label]=rows;interval=[v for f,v in rows.items() if 407<=int(f)<=467];result['summary'][label]={side:{'interval_min_edge_ratio':min(r[side]['edge_ratio_min'] for r in interval),'interval_worst_p99_edge_ratio':max(r[side]['edge_ratio_p99'] for r in interval),'interval_max_edge_ratio':max(r[side]['edge_ratio_max'] for r in interval),'frame_437':rows['437'][side]} for side in side_ids};result['summary'][label]['largest_frame_steps']=sorted(velocities,key=lambda row:-row['max_vertex_step_m'])[:5]
 if label=='after':
  result['skirt_target_max_difference_m']=max_skirt_error;result['projected_target_cache_max_error_m' if projected else 'sleeve_target_actual_solver_max_error_m']=max_solver_error;assert max_skirt_error<1e-6;assert max_solver_error<1e-6
  for o,value in visibility.items():o.hide_viewport=value
  expected=original_hashes if projected else json.loads((out/'sleeve_repair_setup.json').read_text(encoding='utf-8'))['original_mesh_hashes'];actual={}
  for name in expected:
   obj=bpy.data.objects[name];h=hashlib.sha256();data=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',data);h.update(data.tobytes())
   if obj.data.shape_keys:
    for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',data);h.update(data.tobytes())
   actual[name]=h.hexdigest()
  assert actual==expected;result['protected_meshes_and_morphs']=len(actual)
  if projected:
   target.modifiers['Rotation-aware constrained sleeve cache'].filepath='//StableSleeveShapes.pc2';scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
(out/'sleeve_dense_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('SLEEVE_DENSE_SUMMARY',json.dumps(result['summary']),flush=True)
if a.no_render:raise SystemExit(0)
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('StableSleeveReview');data.type='ORTHO';data.ortho_scale=1.1;cam=bpy.data.objects.new('StableSleeveReview',data);scene.collection.objects.link(cam);scene.camera=cam;arm=bpy.data.objects['达妮娅_arm']
for frame in (407,422,432,437,442,447,452,467,496):
 scene.frame_set(frame);center=arm.matrix_world@arm.pose.bones['上半身2'].head+Vector((0,0,-.16))
 for view,d in [('front',(0,-1,.04)),('back',(0,1,.04)),('left_oblique',(1,-1,.05))]:
  cam.location=center+Vector(d).normalized()*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(review/f'{frame}_{view}.png');bpy.ops.render.render(write_still=True)
print('STABLE_SLEEVE_REVIEW_COMPLETE',flush=True)
