"""Continue a true state when only FUTURE collider samples have changed."""
import argparse,sys,json,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession,input_fingerprint,hash_file
p=argparse.ArgumentParser();p.add_argument('--from-run',required=True);p.add_argument('--old-input',required=True);p.add_argument('--new-input',required=True);p.add_argument('--out',required=True);p.add_argument('--max-iterations',type=int);a=p.parse_args();oldrun=Path(a.from_run);old=Path(a.old_input);new=Path(a.new_input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);assert not (out/'positions.npy').exists();pointer=json.loads((oldrun/'latest_state.json').read_text('utf8'));index=pointer['sample'];original=json.loads((oldrun/'input_fingerprint.json').read_text('utf8'));old_config=original['inputs']['config'];config=dict(old_config)
if a.max_iterations is not None:
 assert a.max_iterations>=old_config['max_iterations'];config['max_iterations']=a.max_iterations
oldfp,old_inputs=input_fingerprint(old,old_config);newfp,new_inputs=input_fingerprint(new,config);assert oldfp==pointer['fingerprint']==original['fingerprint'];checks={}
for name,digest in old_inputs.items():
 if name in ['body.npy','anchors.npy','config']:continue
 assert new_inputs[name]==digest,('Changed physics/static data',name);checks[name]=True
for name in ['body.npy','anchors.npy']:
 aa=np.load(old/name,mmap_mode='r');bb=np.load(new/name,mmap_mode='r');assert aa.shape==bb.shape
 for k in range(0,index+1,64):np.testing.assert_array_equal(aa[k:min(k+64,index+1)],bb[k:min(k+64,index+1)])
 checks[name+'_through_checkpoint']=True
(out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf8');checks['only_iteration_budget_may_increase']=all(config[k]==v for k,v in old_config.items() if k!='max_iterations')
source=np.load(oldrun/'positions.npy',mmap_mode='r');dest=np.lib.format.open_memmap(out/'positions.npy',mode='w+',dtype='<f4',shape=source.shape)
for k in range(0,index+1,64):dest[k:min(k+64,index+1)]=source[k:min(k+64,index+1)]
dest.flush();session=DynamicsSession(new,config);session.load(pointer['path'],oldfp);states=out/'checkpoints';states.mkdir();path=states/f'state_{index:06d}.npz';session.save(path,newfp);(out/'latest_state.json').write_text(json.dumps(dict(path=str(path),sample=index,fingerprint=newfp),indent=2),encoding='utf8');(out/'input_fingerprint.json').write_text(json.dumps(dict(fingerprint=newfp,inputs=new_inputs),indent=2),encoding='utf8');history=[r for r in json.loads((oldrun/'progress_history.json').read_text('utf8')) if r['sample']<=index];(out/'progress_history.json').write_text(json.dumps(history,indent=2),encoding='utf8');report=dict(status='TRUE_STATE_PREFIX_FORK_VERIFIED',old_run=str(oldrun),old_fingerprint=oldfp,new_fingerprint=newfp,checkpoint_sample=index,frame=session.manifest['frames'][0]+index*session.manifest['sample_step'],checks=checks,physical_state='original positions and velocities, never fabricated from a display cache',source_change='only future collider trajectory samples may differ');(out/'prefix_fork_proof.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
