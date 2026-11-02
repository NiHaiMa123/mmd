"""Profile whole-board VRAM, busy time and power during three cached renders."""
import argparse,csv,datetime,json,shutil,subprocess,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'gpu_profile.json').exists()
exe=shutil.which('nvidia-smi');assert exe
fields=['timestamp','memory.total','memory.used','utilization.gpu','utilization.memory','power.draw','power.limit','clocks.sm','clocks.mem','temperature.gpu']
phases=[]
def mark(name,fn):
 start=time.time();value=fn();end=time.time();phases.append(dict(phase=name,start_epoch=start,end_epoch=end,elapsed_s=end-start));return value
raw=out/'nvidia_smi_200ms.csv'
with raw.open('w',newline='',encoding='utf8') as stream:
 monitor=subprocess.Popen([exe,'--query-gpu='+','.join(fields),'--format=csv,noheader,nounits','-lms','200'],stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
 try:
  mark('baseline_before_scene',lambda:time.sleep(2))
  def load():
   engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,load_ui=False,use_scripts=False)
   s=bpy.context.scene;prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
   for d in prefs.devices:d.use=d.type=='OPTIX'
   s.cycles.device='GPU';s.cycles.samples=32;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.use_sequencer=False
   s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='16';s.render.image_settings.color_mode='RGB'
   return s
  s=mark('load_scene_and_gpu',load)
  publication=json.loads(Path(s['FullHairCachePublication']).read_text('utf8'));assert publication['published_through_frame']>=352
  for f in [331,346,352]:
   def evaluate():s.frame_set(f);bpy.context.view_layer.update()
   mark(f'evaluate_{f}',evaluate)
   mark(f'render_{f}',lambda:bpy.ops.render.render(write_still=False))
   mark(f'save_png_{f}',lambda:bpy.data.images['Render Result'].save_render(str(out/f'f{f:04d}.png'),scene=s))
   print('GPU_PROFILE_FRAME_DONE',f,flush=True)
  mark('idle_after_renders',lambda:time.sleep(1))
 finally:
  monitor.terminate();monitor.wait(timeout=5)
samples=[]
for row in csv.reader(raw.read_text('utf8').splitlines()):
 if len(row)!=len(fields):continue
 try:
  epoch=datetime.datetime.strptime(row[0].strip(),'%Y/%m/%d %H:%M:%S.%f').timestamp()
  values={k:float(v.strip()) for k,v in zip(fields[1:],row[1:])}
 except ValueError:continue
 phase=next((q['phase'] for q in phases if q['start_epoch']<=epoch<=q['end_epoch']),'between_phases')
 samples.append(dict(epoch=epoch,phase=phase,**values))
assert len(samples)>10,'Insufficient valid NVIDIA samples'
def summary(rows):
 assert rows
 def stat(key):
  vals=[q[key] for q in rows]
  return dict(minimum=min(vals),mean=float(np.mean(vals)),median=float(np.median(vals)),p95=float(np.quantile(vals,.95)),maximum=max(vals))
 return dict(samples=len(rows),vram_used_mib=stat('memory.used'),gpu_busy_percent=stat('utilization.gpu'),memory_io_busy_percent=stat('utilization.memory'),power_watts=stat('power.draw'),sm_clock_mhz=stat('clocks.sm'),temperature_celsius=stat('temperature.gpu'),samples_gpu_busy_at_least_90_percent=sum(q['utilization.gpu']>=90 for q in rows))
baseline=[q for q in samples if q['phase']=='baseline_before_scene'];renders=[q for q in samples if q['phase'].startswith('render_')]
assert baseline and renders
report=dict(source=a.source,source_modified=False,resolution=[1920,1080],samples_per_pixel=32,backend='Cycles GPU OptiX',poll_interval_ms=200,
 measurement_scope='Whole-board NVIDIA measurements including desktop and existing GUI Blender; incremental VRAM is an estimate above pre-load baseline, not per-process accounting',
 total_vram_mib=samples[0]['memory.total'],power_limit_watts=samples[0]['power.limit'],
 baseline=summary(baseline),during_render=summary(renders),whole_run=summary(samples),
 approximate_peak_vram_added_above_baseline_mib=max(q['memory.used'] for q in samples)-float(np.median([q['memory.used'] for q in baseline])),
 phases=phases,samples=samples,
 gpu_busy_definition='Percent of sampled time during which one or more GPU kernels executed; not shader occupancy or percent of theoretical compute throughput',
 nvidia_reference='https://docs.nvidia.com/deploy/nvidia-smi/index.html')
(out/'gpu_profile.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print('GPU_PROFILE_DONE',json.dumps({k:v for k,v in report.items() if k not in ['samples','phases']},ensure_ascii=False),flush=True)
