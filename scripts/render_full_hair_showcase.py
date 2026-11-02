"""Render the original complete character/stage with a fixed full-body camera."""
import argparse,sys,time,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--frames');p.add_argument('--first',type=int,default=1);p.add_argument('--last',type=int,default=450);p.add_argument('--wait-for-publication',action='store_true');p.add_argument('--percentage',type=int,choices=[50,100],default=100);p.add_argument('--samples',type=int,default=32);p.add_argument('--device',choices=['GPU','CPU'],default='GPU');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False);s=bpy.context.scene;print('SHOWCASE_SCENE_OPEN',flush=True);prefs=bpy.context.preferences.addons['cycles'].preferences;
if a.device=='GPU':prefs.compute_device_type='OPTIX';prefs.get_devices()
print('SHOWCASE_DEVICE_READY',a.device,flush=True)
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device=a.device;s.cycles.samples=a.samples;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.image_settings.file_format='PNG';s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=a.percentage;s.render.fps=30
assert s.camera and not s.camera.animation_data and not s.camera.constraints
frames=[int(x) for x in a.frames.split(',')] if a.frames else range(a.first,a.last+1);camera=np.array(s.camera.matrix_world);started=time.monotonic();rows=[]
for f in frames:
 if 'FullHairCachePublication' in s:
  publication_path=Path(bpy.path.abspath(s['FullHairCachePublication']));publication=json.loads(publication_path.read_text('utf8'));wait_started=time.monotonic()
  while f>publication['published_through_frame'] and a.wait_for_publication:
   state=json.loads((Path(publication['run'])/'status.json').read_text('utf8'));assert state['stage']!='FAILED',state;assert time.monotonic()-wait_started<3600,'Publication did not advance';time.sleep(5);publication=json.loads(publication_path.read_text('utf8'))
  assert f<=publication['published_through_frame'],f'Frame {f} is not published by the physical solver yet'
 print('SHOWCASE_EVALUATE_FRAME',f,flush=True);s.frame_set(f);bpy.context.view_layer.update();err=float(np.abs(np.array(s.camera.matrix_world)-camera).max());assert err<1e-9
 target=out/f'f{f:04d}.png';s.render.filepath=str(target)
 if not target.exists():
  print('SHOWCASE_RENDER_BEGIN',f,flush=True);bpy.ops.render.render(write_still=True)
 row=dict(frame=f,available_frames=len(list(out.glob('f*.png'))),elapsed_s=time.monotonic()-started,camera_error=err);rows.append(row);(out/f'progress_{a.first}.json').write_text(json.dumps(row,indent=2),encoding='utf8');print('SHOWCASE_RENDER',json.dumps(row),flush=True)
(out/f'batch_{a.first}.json').write_text(json.dumps(dict(status='COMPLETE',source=a.source,frames=list(frames),seconds=time.monotonic()-started,camera_fixed=True),ensure_ascii=False,indent=2),encoding='utf8')
