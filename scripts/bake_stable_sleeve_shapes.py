"""Constrain actual cached sleeve motion without linear orientation collapse."""
import sys,json,struct,shutil
from pathlib import Path
import bpy,numpy as np
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.sleeve_shape_constraints import rotation_blend,project_strain
from mmd_outfit.stable_sleeve_cloth import bind_clamped_frames
ie=engine('import_export');ie.ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/chest_hd';out=ROOT/'outputs/cynical_cloth15/sleeve_stable';out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;proxy=bpy.data.objects['ClothSimulationSurface'];ref=bpy.data.objects['ClothKinematicReference'];target=bpy.data.objects['ClothShapePreservingTarget'];carrier=bpy.data.objects['ClothUnskinnedVisualCarrier'];mesh=proxy.data;rest=np.array([v.co[:] for v in mesh.vertices]);pin_index=proxy.vertex_groups['ClothPins'].index;pins=np.array([sum(g.weight for g in v.groups if g.group==pin_index) for v in mesh.vertices]);motion=np.array([d.value for d in ref.data.attributes['OutfitClothMotion'].data]);regions={};sleeve_ids=set()
def coords(obj):
 ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);ev.to_mesh_clear();return co.reshape(-1,3)
for side in ('L','R'):
 group=proxy.vertex_groups['腕.'+side].index;ids=sorted(v.index for v in mesh.vertices if any(g.group==group and g.weight>.5 for g in v.groups));sleeve_ids.update(ids);kd=KDTree(len(ids))
 for i in ids:kd.insert(mesh.vertices[i].co,i)
 kd.balance();clusters=[];mapping={}
 for i in ids:
  if i in mapping:continue
  cluster=[j for _,j,d in kd.find_range(mesh.vertices[i].co,1e-5)];k=len(clusters);clusters.append(cluster)
  for j in cluster:mapping[j]=k
 tris=np.array([tuple(mapping[i] for i in f.vertices) for f in mesh.polygons if all(i in mapping for i in f.vertices)]);tris=tris[np.array([len(set(t))==3 for t in tris])];edges=np.array(sorted({tuple(sorted(e)) for t in tris for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0]))}));regions[side]={'ids':ids,'clusters':clusters,'map':mapping,'triangles':tris,'edges':edges,'rest':np.array([rest[c].mean(axis=0) for c in clusters]),'pins':np.array([pins[c].max() for c in clusters]),'motion':np.array([motion[c].mean() for c in clusters])}
visibility={o:o.hide_viewport for o in ie.model_meshes() if o.name!='达妮娅_mesh'}
for o in visibility:o.hide_viewport=True
frames=[];report={'method':'actual cached CLOTH motion, temporally continuous rotation-aware blend, welded seam and local strain/area projection','physical_solver_cache_preserved':True,'body_or_original_mesh_coordinates_changed':False,'frames':[1,496],'welded_target_vertices':sum(len(r['ids'])-len(r['clusters']) for r in regions.values()),'projection':{'iterations':90,'min_edge_ratio':.75,'max_edge_ratio':1.25,'min_area_ratio':.45,'bone_local_temporal_factor':.65,'bone_local_goal_step_limit_m':.045,'max_rotation_change_deg':20},'per_frame':{}}
for frame in range(1,497):
 scene.frame_set(frame);reference=coords(ref);physical=coords(proxy);result=coords(target).copy();row={}
 for side,r in regions.items():
  x=np.array([reference[c].mean(axis=0) for c in r['clusters']]);p=np.array([physical[c].mean(axis=0) for c in r['clusters']]);blend,quaternion=rotation_blend(x,p,r['motion'],r['pins'],previous_rotation=r.get('previous_rotation'),return_rotation=True);r['previous_rotation']=quaternion
  # Filter relative motion in the attachment frame, so body translation and
  # arm rotation remain immediate while the loose sleeve has finite velocity.
  fixed=r['pins']>.999999;c0=r['rest'][fixed].mean(axis=0);c1=x[fixed].mean(axis=0);u,_,vt=np.linalg.svd((r['rest']-c0).T@(x-c1));rotation=u@vt
  if np.linalg.det(rotation)<0:u[:,-1]*=-1;rotation=u@vt
  local=(blend-c1)@rotation.T+c0
  if 'previous_local' in r:
   delta=(local-r['previous_local'])*.65;length=np.linalg.norm(delta,axis=1);delta*=np.minimum(1.,.045/np.maximum(length,1e-12))[:,None];local=r['previous_local']+delta
  blend=(local-c0)@rotation+c1;stable=project_strain(blend,r['rest'],r['edges'],r['triangles'],r['pins'],x);r['previous_local']=(stable-c1)@rotation.T+c0
  for i in r['ids']:result[i]=stable[r['map'][i]]
  e=r['edges'];ratio=np.linalg.norm(stable[e[:,0]]-stable[e[:,1]],axis=1)/np.linalg.norm(r['rest'][e[:,0]]-r['rest'][e[:,1]],axis=1);row[side]={'min_edge_ratio':float(ratio.min()),'max_edge_ratio':float(ratio.max())}
 frames.append(result.astype('<f4'));report['per_frame'][str(frame)]=row
 if frame%100==0:print('SLEEVE_SHAPE_PROJECTION',frame,json.dumps(row),flush=True)
frames=np.array(frames,dtype='<f4');cache=out/'StableSleeveShapes.pc2'
with cache.open('wb') as handle:
 handle.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,len(mesh.vertices),0.,1.,len(frames)));handle.write(frames.tobytes())
for o,value in visibility.items():o.hide_viewport=value
# Original skirt coordinates are copied exactly into this point cache.
for m in list(target.modifiers):target.modifiers.remove(m)
mod=target.modifiers.new('Rotation-aware constrained sleeve cache','MESH_CACHE');mod.cache_format='PC2';mod.filepath=str(cache);mod.play_mode='SCENE';mod.time_mode='FRAME';mod.frame_start=1;mod.frame_scale=1.;mod.deform_mode='OVERWRITE';mod.interpolation='LINEAR'
faces=[f.index for f in mesh.polygons if all(i in sleeve_ids for i in f.vertices)];attrs=carrier.data.attributes;selection={v.index for v in carrier.data.vertices if all(attrs['OutfitBindI'+str(k)].data[v.index].value in sleeve_ids for k in range(3))};report['binding']=bind_clamped_frames(carrier,target,mesh,faces,selection)
errors=[]
for frame in (496,1,47,437,447):
 scene.frame_set(frame);actual=coords(target);errors.append(float(np.abs(actual-frames[frame-1]).max()))
report['cache_reload_read_max_error_m']=max(errors);assert max(errors)<1e-6,errors
shutil.copytree(source/'blendcache_Cynical_Cloth_15s',out/'blendcache_Cynical_Cloth_15s',dirs_exist_ok=True)
for name in ('setup.json','simulation_report.json','cloth_setup.json','CREDITS.txt','chest_repair.json','torso_template.json','chest_geometry_audit.json'):shutil.copyfile(source/name,out/name)
scene['stable_sleeve_cloth_version']=2;scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True);(out/'sleeve_shape_repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('STABLE_SLEEVE_SHAPES_BAKED',report['cache_reload_read_max_error_m'],flush=True)
