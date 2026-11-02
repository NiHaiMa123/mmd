"""Small actual Hair Dynamics benchmark: moving scalp and sweeping sphere."""
import sys,json,argparse,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from animation_contact_tools.native_hair_curves import attach_curve_dynamics,curve_positions_world
p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--no-collision',action='store_true');p.add_argument('--substeps',type=int,default=20);p.add_argument('--iterations',type=int,default=30);p.add_argument('--margin',type=float,default=.003);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=150
bpy.ops.mesh.primitive_plane_add(size=.5,location=(0,0,1));scalp=bpy.context.object;scalp.name='MovingScalp'
bpy.ops.object.curves_empty_hair_add();hair=bpy.context.object;hair.name='FiveIndependentGuideStrands'
for modifier in list(hair.modifiers):hair.modifiers.remove(modifier)
count=5;points=31;xs=np.linspace(-.06,.06,count);world=np.array([(x,0.,1.-.7*j/(points-1)) for x in xs for j in range(points)])
hair.data.add_curves([points]*count);inv=np.asarray(hair.matrix_world.inverted());local=world@inv[:3,:3].T+inv[:3,3]
hair.data.points.foreach_set('position',local.astype(np.float32).ravel());hair.data.set_types(type='POLY')
radius=hair.data.attributes.get('radius') or hair.data.attributes.new('radius','FLOAT','POINT');radius.data.foreach_set('value',np.full(count*points,.0015,dtype=np.float32))
uv=hair.data.attributes.get('surface_uv_coordinate') or hair.data.attributes.new('surface_uv_coordinate','FLOAT2','CURVE');uv.data.foreach_set('vector',np.array([(x/.5+.5,.5) for x in xs],dtype=np.float32).ravel())
hair.data.update_tag()
for frame,x,angle in [(1,0,0),(30,.015,.05),(75,-.015,-.08),(120,.015,.05),(150,0,0)]:
 scalp.location.x=x;scalp.rotation_euler.y=angle;scalp.keyframe_insert('location',frame=frame);scalp.keyframe_insert('rotation_euler',frame=frame)
bpy.ops.mesh.primitive_uv_sphere_add(segments=64,ring_count=32,radius=.105,location=(-.28,-.018,.64));sphere=bpy.context.object;sphere.name='SweepingHandProxy'
for frame,x in [(1,-.28),(20,-.28),(80,.28),(100,.28),(150,-.28)]:
 sphere.location.x=x;sphere.keyframe_insert('location',frame=frame)
for obj in (sphere,scalp):
 action=obj.animation_data.action
 for slot in action.slots:
  for layer in action.layers:
   for strip in layer.strips:
    bag=strip.channelbag(slot)
    if bag:
     for curve in bag.fcurves:
      for key in curve.keyframe_points:key.interpolation='LINEAR'
scene.frame_set(1);bpy.context.view_layer.update();modifier,metadata=attach_curve_dynamics(hair,[] if a.no_collision else [sphere],substeps=a.substeps,iterations=a.iterations,collision_margin=a.margin)
restlength=np.linalg.norm(np.diff(world.reshape(count,points,3),axis=1),axis=2)
frames=[];centres=[];roots=[];rows=[];start=time.monotonic()
for frame in range(1,151):
 scene.frame_set(frame);bpy.context.view_layer.update();co=curve_positions_world(hair).reshape(count,points,3)
 if co.shape!=(count,points,3) or not np.all(np.isfinite(co)):raise RuntimeError('Invalid evaluated Curves positions')
 centre=np.array(sphere.matrix_world.translation);expected=np.array([scalp.matrix_world@Vector((x,0,0)) for x in xs]);edge=co[:,1:]-co[:,:-1];ratio=np.linalg.norm(edge,axis=2)/restlength
 def separation(c,ct):
  begin=c[:,:-1];direction=c[:,1:]-begin;t=np.clip(np.sum((ct-begin)*direction,axis=2)/np.maximum(np.sum(direction*direction,axis=2),1e-16),0,1)
  return np.linalg.norm(begin+t[:,:,None]*direction-ct,axis=2)-.105-.0015
 clearance=float(separation(co,centre).min());temporal=clearance
 if frames:
  for t in (.25,.5,.75):temporal=min(temporal,float(separation(frames[-1]*(1-t)+co*t,centres[-1]*(1-t)+centre*t).min()))
 row={'frame':frame,'min_segment_clearance_m':clearance,'min_interpolated_clearance_m':temporal,'root_error_m':float(np.linalg.norm(co[:,0]-expected,axis=1).max()),'min_edge_ratio':float(ratio.min()),'max_edge_ratio':float(ratio.max())}
 frames.append(co.copy());centres.append(centre);roots.append(expected);rows.append(row)
 if frame%30==0:print('CURVE_HAIR_SAMPLE',json.dumps(row),flush=True)
report={'metadata':metadata,'frames':[1,150],'curve_count':count,'points_per_curve':points,'samples':rows,'max_root_error_m':max(r['root_error_m'] for r in rows),'min_edge_ratio':min(r['min_edge_ratio'] for r in rows),'max_edge_ratio':max(r['max_edge_ratio'] for r in rows),'min_segment_clearance_m':min(r['min_segment_clearance_m'] for r in rows),'min_interpolated_clearance_m':min(r['min_interpolated_clearance_m'] for r in rows),'seconds':time.monotonic()-start,'continuous_collision_proven':False,'polygon_hair_mapped':False,'self_collision_tested':False}
report['benchmark_pass']=not a.no_collision and report['max_root_error_m']<.0005 and report['min_edge_ratio']>.97 and report['max_edge_ratio']<1.03 and report['min_interpolated_clearance_m']>-.001
np.savez_compressed(out/'curve_motion.npz',coordinates=frames,collider_centres=centres,expected_roots=roots,rest_coordinates=world)
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'NativeCurve_LiveBenchmark.blend'),compress=True)
print('CURVE_HAIR_BENCHMARK',json.dumps({k:v for k,v in report.items() if k not in ('samples','metadata')}),flush=True)
