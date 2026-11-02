"""Render existing baked motion only, with correctly timed output samples."""
import argparse,json,math,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--start-seconds',type=float,default=10);p.add_argument('--duration',type=float,default=3);p.add_argument('--fps',type=int,default=24);p.add_argument('--samples',type=int,default=24);p.add_argument('--half-second-gallery',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
s=bpy.context.scene;assert s.render.fps==30 and s.render.fps_base==1
if not s.get('ReviewExistingJiggleBakeOnly'):
 receipt=json.loads((Path(a.source).parent/'bake_report.json').read_text('utf8'));assert Path(receipt['blend']).resolve()==Path(a.source).resolve();assert bpy.data.objects['东雪莲x达妮娅_骨架'].animation_data.action.name==receipt['action']
assert not s.rigidbody_world or not s.rigidbody_world.enabled
assert not any('jiggle' in getattr(f,'__module__','').lower() for f in list(bpy.app.handlers.frame_change_pre)+list(bpy.app.handlers.frame_change_post))
assert s.camera and not s.camera.animation_data and not s.camera.constraints
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':assert Path(bpy.path.abspath(md.filepath)).is_file()
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=a.samples;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.use_sequencer=False;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8';s.render.image_settings.color_mode='RGB';s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
count=round(a.duration*a.fps);camera=np.array(s.camera.matrix_world);started=time.monotonic();rows=[];folder=out/'frames';folder.mkdir(exist_ok=True)
def render(frame,target):
 assert 1<=frame<=450,frame
 s.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update();assert np.abs(np.array(s.camera.matrix_world)-camera).max()<1e-9
 s.render.filepath=str(target)
 if not target.exists():bpy.ops.render.render(write_still=True)
for index in range(1,count+1):
 seconds=a.start_seconds+(index-1)/a.fps;f=1+30*seconds;target=folder/f'f{index:04d}.png';render(f,target)
 row=dict(output_frame=index,original_seconds=seconds,source_frame=f,elapsed_s=time.monotonic()-started);rows.append(row);(out/'render_progress.json').write_text(json.dumps(row,indent=2),'utf8');print('BAKED_HAIR_REVIEW_RENDER',json.dumps(row),flush=True)
gallery=[]
if a.half_second_gallery:
 stills=out/'gallery';stills.mkdir(exist_ok=True)
 for frame in list(range(151,437,15))+[450]:
  target=stills/f'f{frame:04d}.png';render(frame,target);gallery.append(dict(frame=frame,seconds=(frame-1)/30,path=str(target)));print('BAKED_HAIR_REVIEW_STILL',frame,flush=True)
report=dict(status='BAKED_HAIR_REVIEW_RENDER_COMPLETE',source=a.source,source_seconds=[a.start_seconds,a.start_seconds+a.duration],duration_seconds=a.duration,resolution=[1920,1080],output_fps=a.fps,source_fps=30,samples=a.samples,frames=rows,gallery=gallery,elapsed_s=time.monotonic()-started,new_simulation=False,physics_acceptance=False,shutdown_forbidden=True)
(out/'render_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
