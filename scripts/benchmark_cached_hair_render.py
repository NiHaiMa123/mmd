"""Read-only cached-frame benchmark; separate rendering from PNG encoding."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'benchmark.json').exists()
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
s=bpy.context.scene
assert s.camera and not s.camera.animation_data and not s.camera.constraints
publication=json.loads(Path(s['FullHairCachePublication']).read_text('utf8'));assert publication['published_through_frame']>=352
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
s.cycles.device='GPU';s.cycles.use_denoising=True;s.render.use_persistent_data=True
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.use_sequencer=False
config=dict(source=a.source,resolution=[1920,1080],device='OPTIX',denoising=s.cycles.denoiser,
 adaptive_sampling=s.cycles.use_adaptive_sampling,noise_threshold=s.cycles.adaptive_threshold,
 png_compression=s.render.image_settings.compression,
 devices=[dict(name=d.name,type=d.type,use=d.use) for d in prefs.devices],source_modified=False)
rows=[];began=time.perf_counter()
for samples,depth in [(32,'16'),(32,'8'),(24,'8'),(16,'8')]:
 s.cycles.samples=samples;s.render.image_settings.color_depth=depth
 for frame in [331,346,352]:
  t0=time.perf_counter();s.frame_set(frame);bpy.context.view_layer.update();t1=time.perf_counter()
  bpy.ops.render.render(write_still=False);t2=time.perf_counter()
  target=out/f's{samples}_png{depth}_f{frame}.png';bpy.data.images['Render Result'].save_render(str(target),scene=s);t3=time.perf_counter()
  row=dict(samples=samples,png_depth=int(depth),frame=frame,evaluation_s=t1-t0,render_s=t2-t1,png_save_s=t3-t2,total_s=t3-t0,bytes=target.stat().st_size,cold_first_render=not rows)
  rows.append(row);(out/'progress.json').write_text(json.dumps(row,indent=2),'utf8');print('RENDER_BENCH',json.dumps(row),flush=True)
summary=[]
for samples,depth in [(32,16),(32,8),(24,8),(16,8)]:
 selected=[r for r in rows if r['samples']==samples and r['png_depth']==depth and not r['cold_first_render']]
 summary.append(dict(samples=samples,png_depth=depth,frames=len(selected),mean_total_s=float(np.mean([r['total_s'] for r in selected])),mean_render_s=float(np.mean([r['render_s'] for r in selected])),mean_png_save_s=float(np.mean([r['png_save_s'] for r in selected])),mean_bytes=float(np.mean([r['bytes'] for r in selected]))))
report=dict(config=config,rows=rows,summary=summary,elapsed_s=time.perf_counter()-began,benchmark_only=True,source_modified=False)
(out/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('BENCHMARK_DONE',json.dumps(summary),flush=True)
