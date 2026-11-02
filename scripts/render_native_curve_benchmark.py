"""Deterministic 1080p replay of measured curves, independent of live sim caches."""
import sys,argparse,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--stills',action='store_true');p.add_argument('--save-replay',action='store_true');p.add_argument('--cache-only',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);source=np.load(Path(a.control)/'curve_motion.npz');candidate=np.load(Path(a.candidate)/'curve_motion.npz');bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.world=bpy.data.worlds.new('BenchmarkWorld')
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.fps=30;scene.render.image_settings.file_format='PNG';scene.world.color=(.045,.055,.07);s=scene.display.shading;s.light='STUDIO';s.color_type='MATERIAL';s.show_shadows=True;s.show_cavity=True;s.background_type='WORLD'
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);return m
blue=material('Collision-enabled curves',(.1,.55,.9));orange=material('No collision control',(.95,.28,.05));gray=material('Moving sphere',(.43,.49,.55));white=material('Root attachment',(.8,.85,.9));panels=[]
for index,(data,mat) in enumerate(((source,orange),(candidate,blue))):
 offset=np.array([-.52 if index==0 else .52,0,0]);curves=bpy.data.curves.new('Measured curve replay','CURVE');curves.dimensions='3D';curves.bevel_depth=.0025;curves.bevel_resolution=3;obj=bpy.data.objects.new('Control' if index==0 else 'Native Hair Dynamics',curves);scene.collection.objects.link(obj);curves.materials.append(mat)
 for strand in data['coordinates'][0]:
  spline=curves.splines.new('POLY');spline.points.add(len(strand)-1)
 bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=.105);sphere=bpy.context.object;sphere.data.materials.append(gray)
 for poly in sphere.data.polygons:poly.use_smooth=True
 roots=[]
 for root in data['expected_roots'][0]:
  bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.005);marker=bpy.context.object;marker.data.materials.append(white);roots.append(marker)
 panels.append((data,offset,curves,sphere,roots))
camdata=bpy.data.cameras.new('BenchmarkCamera');camdata.type='ORTHO';camdata.ortho_scale=2.05;camera=bpy.data.objects.new('BenchmarkCamera',camdata);scene.collection.objects.link(camera);camera.location=(.12,-4,.85);target=Vector((0,0,.65));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
frames=[1,35,60,90,120,145] if a.stills else range(1,len(candidate['coordinates'])+1)
for frame in frames:
 scene.frame_set(frame)
 for data,offset,curves,sphere,roots in panels:
  for spline,strand in zip(curves.splines,data['coordinates'][frame-1]):
   spline.points.foreach_set('co',np.c_[strand+offset,np.ones(len(strand))].ravel())
   if a.save_replay:
    for point in spline.points:point.keyframe_insert('co',frame=frame)
  sphere.location=data['collider_centres'][frame-1]+offset
  if a.save_replay:sphere.keyframe_insert('location',frame=frame)
  for marker,root in zip(roots,data['expected_roots'][frame-1]):
   marker.location=root+offset
   if a.save_replay:marker.keyframe_insert('location',frame=frame)
 if not a.cache_only:scene.render.filepath=str(out/f'{frame:04}.png');bpy.ops.render.render(write_still=True)
 if frame%30==0:print('CURVE_BENCHMARK_RENDER',frame,flush=True)
(out/'replay.json').write_text(json.dumps({'source':a.control,'candidate':a.candidate,'frames':list(frames),'resolution':[1920,1080],'left':'no collision','right':'native hair dynamics','original_measured_coordinates':True},indent=2),encoding='utf8')
if a.save_replay:
 for action in bpy.data.actions:
  for layer in action.layers:
   for strip in layer.strips:
    for slot in action.slots:
     bag=strip.channelbag(slot)
     if bag:
      for curve in bag.fcurves:
       for key in curve.keyframe_points:key.interpolation='LINEAR'
 scene.frame_start=1;scene.frame_end=len(candidate['coordinates']);scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'NativeCurve_BakedReplay.blend'),compress=True)
