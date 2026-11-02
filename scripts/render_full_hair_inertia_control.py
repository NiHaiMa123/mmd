"""Render a full-character 3-second native-cache control at normal speed."""
import argparse,json,math,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--run',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run);out=run/'render';out.mkdir(exist_ok=True)
result=json.loads((run/'result.json').read_text('utf8'));assert result['frames']==[1,91] and result['stop'] is None,'Complete short control required'
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;assert s.render.fps==30 and not s.camera.animation_data and not s.camera.constraints
assert all(not md.show_render for ob in bpy.data.objects for md in ob.modifiers if md.type=='CLOTH'),'Only recorded native output may render'
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   md.filepath=bpy.path.abspath(md.filepath);assert Path(md.filepath).is_file(),md.filepath
publication=json.loads(Path(s['FullHairCachePublication']).read_text('utf8'));assert publication['published_through_frame']==91
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.use_sequencer=False
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8';s.render.image_settings.color_mode='RGB'
frames=out/'frames';frames.mkdir(exist_ok=True);camera=np.array(s.camera.matrix_world);started=time.monotonic();rows=[]
for index in range(1,73):
 f=1+(index-1)*1.25;s.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();assert np.max(np.abs(np.array(s.camera.matrix_world)-camera))<1e-9
 target=frames/f'f{index:04d}.png';s.render.filepath=str(target)
 if not target.exists():bpy.ops.render.render(write_still=True)
 row=dict(output_frame=index,source_frame=f,seconds=(index-1)/24,elapsed_s=time.monotonic()-started);rows.append(row)
 (out/'progress.json').write_text(json.dumps(row,indent=2),'utf8');print('INERTIA_CONTROL_RENDER',json.dumps(row),flush=True)
report=dict(status='CONTROL_72_FRAMES_COMPLETE',preset=result['preset'],control_only=True,production_motion=False,resolution=[1920,1080],output_fps=24,source_fps=30,cycles_samples=24,duration_seconds=3,source_blend=result['blend'],frames=rows,elapsed_s=time.monotonic()-started,shutdown_forbidden=True)
(out/'render_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
