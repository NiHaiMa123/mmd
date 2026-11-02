"""Functional tests of Blender's unchanged bundled Hair Dynamics asset.

The long-segment test keeps end points clear while a sphere crosses the edge.
The sweep test is a fast moving closed collider. No solver is implemented here.
"""
import sys,json,time,argparse,numpy as np
from pathlib import Path
import bpy
from mathutils import Vector
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from animation_contact_tools.native_hair_curves import attach_curve_dynamics,curve_positions_world
p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True)
def linear(obj):
 for layer in obj.animation_data.action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in bag.fcurves:
     for key in fc.keyframe_points:key.interpolation='LINEAR'
def clearance(co,center,radius):
 start=co[:,:-1];v=np.diff(co,axis=1);t=np.clip(np.sum((center-start)*v,axis=2)/np.maximum((v*v).sum(2),1e-15),0,1)
 return np.linalg.norm(start+t[:,:,None]*v-center,axis=2)-radius-.0015
results=[]
for case,npoints,radius,cz,moves in [
 ('sparse_segment_contact',9,.04,.60625,[(1,-.28),(15,-.28),(75,.28),(90,.28)]),
 ('fast_closed_collider_sweep',31,.105,.64,[(1,-.28),(15,-.28),(25,.28),(90,.28)]),
]:
 bpy.ops.wm.read_factory_settings(use_empty=True);s=bpy.context.scene;s.render.fps=30;s.frame_end=90
 bpy.ops.mesh.primitive_plane_add(size=.5,location=(0,0,1));scalp=bpy.context.object
 bpy.ops.object.curves_empty_hair_add();hair=bpy.context.object
 for mod in list(hair.modifiers):hair.modifiers.remove(mod)
 xs=np.array([-.02,0,.02]);count=len(xs);world=np.array([(x,0,1-.7*j/(npoints-1)) for x in xs for j in range(npoints)])
 hair.data.add_curves([npoints]*count);inv=np.array(hair.matrix_world.inverted());hair.data.points.foreach_set('position',np.asarray(world@inv[:3,:3].T+inv[:3,3],np.float32).ravel());hair.data.set_types(type='POLY')
 ra=hair.data.attributes.get('radius') or hair.data.attributes.new('radius','FLOAT','POINT');ra.data.foreach_set('value',np.full(len(world),.0015,np.float32))
 uv=hair.data.attributes.get('surface_uv_coordinate') or hair.data.attributes.new('surface_uv_coordinate','FLOAT2','CURVE');uv.data.foreach_set('vector',np.asarray([(x/.5+.5,.5) for x in xs],np.float32).ravel());hair.data.update_tag()
 bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=radius,location=(moves[0][1],0,cz));collider=bpy.context.object
 for f,x in moves:collider.location.x=x;collider.keyframe_insert('location',frame=f)
 linear(collider);s.frame_set(1);bpy.context.view_layer.update()
 md,meta=attach_curve_dynamics(hair,[collider],substeps=60,iterations=120,bendiness=.25,root_bendiness=.2,collision_margin=.003)
 rest=np.linalg.norm(np.diff(world.reshape(count,npoints,3),axis=1),axis=2);rows=[];motion=[];previous=None;previouscenter=None;started=time.monotonic()
 for f in range(1,91):
  s.frame_set(f);bpy.context.view_layer.update();co=curve_positions_world(hair).reshape(count,npoints,3);center=np.array(collider.matrix_world.translation)
  assert np.isfinite(co).all();sep=float(clearance(co,center,radius).min());temporal=sep
  if previous is not None:
   for t in [.25,.5,.75]:temporal=min(temporal,float(clearance(previous*(1-t)+co*t,previouscenter*(1-t)+center*t,radius).min()))
  ratios=np.linalg.norm(np.diff(co,axis=1),axis=2)/rest
  rows.append(dict(frame=f,minimum_segment_clearance_m=sep,quarter_frame_interpolated_clearance_m=temporal,edge_ratio_min=float(ratios.min()),edge_ratio_max=float(ratios.max())))
  previous=co.copy();previouscenter=center.copy();motion.append(co.copy())
  if f%15==0:print('NATIVE_CONTACT_TEST',case,f,sep,flush=True)
 report=dict(case=case,metadata=meta,frames=90,min_segment_clearance_m=min(r['minimum_segment_clearance_m'] for r in rows),min_interpolated_clearance_m=min(r['quarter_frame_interpolated_clearance_m'] for r in rows),edge_ratio_min=min(r['edge_ratio_min'] for r in rows),edge_ratio_max=max(r['edge_ratio_max'] for r in rows),rows=rows,elapsed_s=time.monotonic()-started,not_a_full_character_acceptance=True)
 # A visible centimetre-scale miss rejects the backend immediately. Smaller
 # errors are reported without using tiny numerical tolerances as stop gates.
 report['centimetre_failure']=report['min_interpolated_clearance_m']<-.01 or report['edge_ratio_max']>1.3 or report['edge_ratio_min']<.7
 (out/(case+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');np.savez_compressed(out/(case+'.npz'),coordinates=motion,rest=world)
 results.append({k:v for k,v in report.items() if k!='rows'})
 if report['centimetre_failure']:break
(out/'result.json').write_text(json.dumps(dict(results=results,stage='NATIVE_HAIR_CONTACT_FUNCTIONAL_TEST',new_character_physics=False),ensure_ascii=False,indent=2),'utf8')
print('NATIVE_CONTACT_FUNCTIONAL_TEST_COMPLETE',json.dumps(results,ensure_ascii=False),flush=True)
