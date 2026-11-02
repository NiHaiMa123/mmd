"""Versioned collider upgrade from a verified real checkpoint, retaining source."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession,input_fingerprint,hash_file
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--from-run',required=True);p.add_argument('--archive',required=True);p.add_argument('--sample',type=int,required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);old=Path(a.from_run);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);assert not (out/'positions.npy').exists();original=json.loads((old/'input_fingerprint.json').read_text('utf8'));oldfp=original['fingerprint'];inputs=original['inputs'];config=inputs['config'];archive=Path(a.archive)
for name,digest in inputs.items():
 if name in ['algorithm','config']:continue
 assert hash_file(src/name)==digest,name
for name,digest in inputs['algorithm'].items():assert hash_file(archive/(Path(name).stem+'_single_field.py'))==digest,name
checkpoint=old/'checkpoints'/f'state_{a.sample:06d}.npz'
with np.load(checkpoint) as z:assert str(z['fingerprint'])==oldfp and int(z['index'])==a.sample
fingerprint,newinputs=input_fingerprint(src,config);session=DynamicsSession(src,config);session.load(checkpoint,oldfp);positions=np.load(old/'positions.npy',mmap_mode='r');dest=np.lib.format.open_memmap(out/'positions.npy',mode='w+',dtype='<f4',shape=positions.shape)
for k in range(0,a.sample+1,64):dest[k:min(k+64,a.sample+1)]=positions[k:min(k+64,a.sample+1)]
dest.flush();states=out/'checkpoints';states.mkdir();state=states/checkpoint.name;session.save(state,fingerprint);(out/'config.json').write_text(json.dumps(session.config,indent=2),encoding='utf8');(out/'input_fingerprint.json').write_text(json.dumps(dict(fingerprint=fingerprint,inputs=newinputs),indent=2),encoding='utf8');(out/'latest_state.json').write_text(json.dumps(dict(path=str(state),sample=a.sample,fingerprint=fingerprint),indent=2),encoding='utf8');history=[r for r in json.loads((old/'progress_history.json').read_text('utf8')) if r['sample']<=a.sample];(out/'progress_history.json').write_text(json.dumps(history,indent=2),encoding='utf8');proof=dict(status='TRUE_STATE_PREFIX_FORK_VERIFIED',old_fingerprint=oldfp,new_fingerprint=fingerprint,checkpoint_sample=a.sample,frame=session.manifest['frames'][0]+a.sample*session.manifest['sample_step'],invalidate_after_checkpoint=True,versioned_upgrade='Original single-field code archived and checked by SHA256; identical input and real positions/velocities; independent contact volumes and finite-triangle witnesses prepare before profile-defined protected contacts',original_code_sha256=inputs['algorithm'],new_code_sha256=newinputs['algorithm']);(out/'prefix_fork_proof.json').write_text(json.dumps(proof,indent=2),encoding='utf8');print('CONTACT_BACKEND_REAL_STATE_UPGRADED',fingerprint,flush=True)
