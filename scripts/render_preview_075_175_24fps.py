"""Render 240 correctly timed samples from 30 Hz physics at 24 output fps."""
import argparse,json,math,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--physics',required=True);p.add_argument('--out',required=True);p.add_argument('--keyframes-only',action='store_true');p.add_argument('--first-output',type=int,default=1);p.add_argument('--last-output',type=int,default=240)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);physics=Path(a.physics);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
r=json.loads((physics/'result.json').read_text('utf8'));assert r['frames']==[1,526] and r['stop'] is None,'Complete preview physics required'
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;assert s.render.fps==30 and not s.camera.animation_data and not s.camera.constraints
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.use_sequencer=False
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8';s.render.image_settings.color_mode='RGB'
assert all(not md.show_render for ob in bpy.data.objects for md in ob.modifiers if md.type=='CLOTH'),'Render only native output caches'
publication=json.loads(Path(s['FullHairCachePublication']).read_text('utf8'));assert publication['published_through_frame']==526
plan=dict(source_seconds=[7.5,17.5],duration_seconds=10,source_fps=30,output_fps=24,output_frames=240,resolution=[1920,1080],cycles_samples=24,png_bit_depth=8,source_blend=r['blend'],physics_result=str(physics/'result.json'),sampling='source_frame=226+(output_frame-1)*1.25; native motion speed retained',frames=[dict(output_frame=i+1,source_frame=226+i*1.25,source_seconds=7.5+i/24) for i in range(240)],known_hair_strain_retained=True,physics_accepted=False,shutdown_forbidden=True)
if (out/'render_plan.json').exists():assert json.loads((out/'render_plan.json').read_text('utf8'))==plan
else:(out/'render_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf8')
s['PreviewOutputFPS']=24;s['PreviewSourceFPS']=30;s['PreviewSourceSeconds']='7.5-17.5';s['PreviewOutputFrames']=240;s['ShutdownForbidden']=True
s.frame_start=226;s.frame_end=526
blend=out/'完整角色_7.5至17.5秒_24fps预览源工程.blend'
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   md.filepath=bpy.path.abspath(md.filepath)
   assert Path(md.filepath).is_file(),('Missing physical cache',ob.name,md.filepath)
if not blend.exists():
 bpy.ops.wm.save_as_mainfile(filepath=str(blend))
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':assert Path(bpy.path.abspath(md.filepath)).is_file()
frames=out/'frames';frames.mkdir(exist_ok=True);camera=np.array(s.camera.matrix_world);started=time.monotonic();start_epoch=time.time();rows=[]
assert 1<=a.first_output<=a.last_output<=240
chunk=not a.keyframes_only and (a.first_output,a.last_output)!=(1,240)
indices=[1,85,121,181,240] if a.keyframes_only else range(a.first_output,a.last_output+1)
for index in indices:
 row=plan['frames'][index-1];f=row['source_frame'];s.frame_set(math.floor(f),subframe=f%1);bpy.context.view_layer.update();error=float(np.abs(np.array(s.camera.matrix_world)-camera).max());assert error<1e-9
 target=frames/f'f{index:04d}.png';s.render.filepath=str(target)
 if not target.exists():bpy.ops.render.render(write_still=True)
 progress=dict(**row,available_frames=len(list(frames.glob('f*.png'))),elapsed_s=time.monotonic()-started,camera_error=error)
 rows.append(progress);progress_name='render_progress.json' if a.keyframes_only else f'render_progress_{a.first_output}.json';(out/progress_name).write_text(json.dumps(progress,indent=2),'utf8');print('PREVIEW_RENDER',json.dumps(progress),flush=True)
report=dict(status='KEYFRAMES_COMPLETE' if a.keyframes_only else 'OUTPUT_FRAME_RANGE_COMPLETE' if chunk else 'ALL_240_OUTPUT_FRAMES_COMPLETE',source_blend=str(blend),resolution=[1920,1080],fps=24,samples=24,elapsed_s=time.monotonic()-started,start_epoch=start_epoch,end_epoch=time.time(),frames=rows)
report_name='keyframes_report.json' if a.keyframes_only else f'render_chunk_{a.first_output}_{a.last_output}.json' if chunk else 'render_report.json'
(out/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print('PREVIEW_RENDER_COMPLETE',report['status'],flush=True)
