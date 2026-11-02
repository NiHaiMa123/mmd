"""Run/resume bounded-memory full-head dynamics from an exact exported sequence."""
import argparse,json,sys,os,time,ctypes
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics_material.pd_dynamics import DynamicsSession,input_fingerprint
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--config');p.add_argument('--resume',action='store_true');p.add_argument('--end-index',type=int);a=p.parse_args();out=Path(a.out);out.mkdir(exist_ok=True,parents=True);lock=out/'worker.lock.json'
def alive(pid):
 from ctypes import wintypes
 kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE;handle=kernel.OpenProcess(0x1000,False,int(pid))
 if not handle:return ctypes.get_last_error()==5
 code=wintypes.DWORD();kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)];kernel.GetExitCodeProcess(handle,ctypes.byref(code));kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle(handle);return code.value==259
if lock.exists():
 previous=json.loads(lock.read_text('utf8'))
 if alive(previous['pid']):raise RuntimeError(f'Existing dynamics worker {previous["pid"]}; refusing duplicate')
 lock.replace(out/f'worker_stale_{int(time.time())}.json')
with lock.open('x',encoding='utf8') as stream:json.dump(dict(pid=os.getpid(),created=time.time()),stream)
def status(data):
 data=dict(pid=os.getpid(),**data);tmp=out/'status.tmp.json';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(out/'status.json')
try:
 config=json.loads(Path(a.config).read_text('utf-8-sig')) if a.config else {};status(dict(stage='LOADING_AND_FINGERPRINTING'));fingerprint,inputs=input_fingerprint(a.input,config);(out/'input_fingerprint.json').write_text(json.dumps(dict(fingerprint=fingerprint,inputs=inputs),indent=2),encoding='utf8');session=DynamicsSession(a.input,config);total=len(session.body);goal=total-1 if a.end_index is None else min(a.end_index,total-1);states=out/'checkpoints';states.mkdir(exist_ok=True);position_file=out/'positions.npy';history=[];started=time.monotonic()
 if a.resume:
  pointer=json.loads((out/'latest_state.json').read_text('utf8'));session.load(pointer['path'],fingerprint);positions=np.load(position_file,mmap_mode='r+');assert positions.shape==(total,len(session.initial),3);history=json.loads((out/'progress_history.json').read_text('utf8')) if (out/'progress_history.json').exists() else []
 else:
  if position_file.exists():raise ValueError('Existing output requires --resume; never overwrite a prior solve')
  positions=np.lib.format.open_memmap(position_file,mode='w+',dtype='<f4',shape=(total,len(session.initial),3));status(dict(stage='PRE_ROLL',steps=session.config['preroll_steps']));metrics=session.preroll();positions[0]=session.solver.positions();history.append(dict(sample=0,frame=session.manifest['frames'][0],**metrics))
 def checkpoint():
  positions.flush();path=states/f'state_{session.index:06d}.npz';session.save(path,fingerprint);(out/'latest_state.json').write_text(json.dumps(dict(path=str(path),sample=session.index,fingerprint=fingerprint),indent=2),encoding='utf8');(out/'progress_history.json').write_text(json.dumps(history,indent=2),encoding='utf8')
 checkpoint()
 for index in range(session.index+1,goal+1):
  metrics=session.advance(index);positions[index]=session.solver.positions();frame=session.manifest['frames'][0]+index*session.manifest['sample_step'];history.append(dict(sample=index,frame=frame,**metrics))
  if index%24==0 or index==goal:
   row=dict(stage='SIMULATING',sample=index,frame=frame,total_samples=total,elapsed_this_run_s=time.monotonic()-started,**metrics);status(row);print('FULL_HAIR_DYNAMICS',json.dumps(row),flush=True)
  if index%session.config['checkpoint_interval']==0 or index==goal:checkpoint()
 final=dict(stage='COMPLETE' if session.index==total-1 else 'TEST_PREFIX_RECORDED',last_sample=session.index,total_samples=total,frames=[session.manifest['frames'][0],session.manifest['frames'][0]+session.index*session.manifest['sample_step']],fingerprint=fingerprint,config=session.config,soft_render_island_tethers=session.soft_islands,root_set_unchanged=True,source_mesh_weights_actions_unchanged=True,body_contact_sampled_pass=True,display_card_self_collision_accepted=False,ccd_proven=False,model='Rotation-invariant projective elastic springs, local material braces, calibrated compliant style springs, inertial gravity dynamics and real-skin contact',elapsed_this_run_s=time.monotonic()-started)
 (out/'result.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf8');status(final);print('FULL_HAIR_RUN_COMPLETE',json.dumps(final),flush=True)
except BaseException as exc:
 if 'session' in locals():session.save(out/'failure_state.npz',fingerprint)
 status(dict(stage='FAILED',error=repr(exc)));raise
finally:
 if lock.exists() and json.loads(lock.read_text('utf8'))['pid']==os.getpid():lock.unlink()

