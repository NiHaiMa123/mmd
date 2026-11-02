"""Durable one-shot resume, checkpoints, native validation and 1080p review."""
import json,os,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];phase=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/surface_proxy_20261029';src=phase/'full_feedback_ppf_transport';delivery=phase/'continuous_delivery';delivery.mkdir(parents=True,exist_ok=True);status_file=delivery/'worker_status.json'
# Check the real Windows process before touching another worker's status.
if status_file.exists():
 import ctypes
 from ctypes import wintypes
 previous=json.loads(status_file.read_text('utf8'));pid=previous.get('pid')
 if pid and pid!=os.getpid():
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE;kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.CloseHandle.argtypes=[wintypes.HANDLE];handle=kernel.OpenProcess(0x1000,False,pid)
  if handle:
   exit_code=wintypes.DWORD();ok=kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code));kernel.CloseHandle(handle)
   if not ok or exit_code.value==259:raise SystemExit(f'Existing delivery worker {pid}; leave its task and status intact')
def status(stage,**details):
 data=dict(stage=stage,pid=os.getpid(),updated_local=time.strftime('%Y-%m-%d %H:%M:%S'),all_hair_accepted=False,**details);temp=status_file.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(status_file);print('DELIVERY_STAGE',stage,flush=True)
def command(stage,args):
 status(stage)
 with (delivery/(stage+'.log')).open('w',encoding='utf8') as log:subprocess.run(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
try:
 status('RECOVERING_CHECKPOINT');native=ROOT/'tools/ppf/native';sys.path.insert(0,str(native));dll=os.add_dll_directory(str(native/'bin'))
 from frontend import App,_cbor_bridge_ as cbor
 App.get_data_dirpath=staticmethod(lambda:str(src/'runtime'));session=App.recover('real_outfit');saved=session.get.saved()
 if not saved:raise RuntimeError('No valid native checkpoint; refusing to fake velocity/state from output positions')
 manifest=json.loads((src/'manifest.json').read_text('utf8'));fps=120;frames=round((manifest['source_frames'][1]-manifest['source_frames'][0])/manifest['fps']*fps);checkpoint=max(saved)
 session.session.param.set('dt',.008).set('auto-save',120).set('keep-states',20).set('save-state-on-finish',True);session.session.param.export(session.info.path)
 status('RESUMING_NATIVE',checkpoint=checkpoint,requested_output_frames=frames,output=session.output.path)
 session.resume(frame=checkpoint,force=False,blocking=True)
 latest=session.get.latest_frame()
 if not session.finished() or latest<frames:raise RuntimeError(f'Native run incomplete: last output {latest}, requested {frames}')
 mapping=cbor.loads_vertex_map((Path(session.output.path).parent/'map.pickle').read_bytes());ids=np.asarray(mapping['cloth'],dtype=int);positions=[]
 for f in range(frames+1):
  got=session.get.vertex(f)
  if got is None:raise RuntimeError(f'Missing completed native frame {f}')
  positions.append(got[0][ids])
 np.save(src/'PPFVolume.npy',np.asarray(positions,dtype='<f4'));native_status=dict(status='FINISHED',frames=frames,output_fps=fps,source_fps=manifest['fps'],time_step_s=.008,initial_time_step_s=.003,resumed_from_checkpoint=checkpoint,hard_pins=21,soft_pins=0,contact_exemptions=0,allow_intersection=False,output=session.output.path,auto_save_output_interval=120,last_output_frame=latest)
 (src/'solve_status.json').write_text(json.dumps(native_status,indent=2),encoding='utf8')
 blender=r'D:\software\blender\5.2.1\blender.exe';candidate_run=phase/'full_resumed_display'
 def blend(script,args):return [blender,'--factory-startup','-b','-t','3','--python-exit-code','1','--python',str(ROOT/'scripts'/script),'--',*args]
 command('IMPORT_FULL_HAIR',blend('import_ppf_volume_hair.py',['--input',str(src),'--out',str(candidate_run)]))
 command('VERIFY_FULL_HAIR',blend('verify_surface_proxy_cache.py',['--run',str(candidate_run),'--step','.125','--containment']))
 command('VERIFY_SOURCE',blend('verify_bundle_source_integrity.py',['--run',str(candidate_run)]))
 check=json.loads((candidate_run/'independent_validation.json').read_text('utf8'));integrity=json.loads((candidate_run/'source_integrity.json').read_text('utf8'));report=json.loads((candidate_run/'report.json').read_text('utf8'))
 passed=check['selected_bundle_sampled_pass'] and check['frames']==[1.,450.] and check['sample_count']==3593
 command('RENDER_MULTIVIEW',blend('render_arm_hair_feedback.py',['--stills','--component','3','--zoom','1.9','--target-z','-.15','--frames','69,175,242,245,325.75,375,450','--before',str(phase.parent/'multi_bundle/left_partial_assembled/SelectedBundle_SurfaceCorrective_NotFullyAccepted.blend'),'--after',report['candidate'],'--out',str(delivery/'review1080')]))
 result=dict(status='LEFT_BUNDLE_FULL_CLIP_SAMPLED_PASS_REQUIRES_VISUAL_REVIEW' if passed else 'LEFT_BUNDLE_FULL_CLIP_UNRESOLVED',candidate=report['candidate'],validation=str(candidate_run/'independent_validation.json'),source_integrity=str(candidate_run/'source_integrity.json'),review=str(delivery/'review1080'),frames=check['frames'],failed_collision_samples=check['failed_collision_samples'],failed_strain_samples=check['failed_strain_samples'],failed_containment_samples=check['failed_containment_samples'],all_hair_accepted=False,ccd_proven=False)
 (delivery/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');status('FINISHED',result=result)
except BaseException as exc:
 status('FAILED',error=repr(exc));raise
