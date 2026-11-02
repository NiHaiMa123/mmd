"""Replay a real state checkpoint and compare with the continuous trajectory."""
import argparse,sys,json,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.dynamics import DynamicsSession,input_fingerprint
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--run',required=True);p.add_argument('--sample',type=int,required=True);p.add_argument('--steps',type=int,default=8);p.add_argument('--out',required=True);a=p.parse_args();run=Path(a.run);saved=json.loads((run/'input_fingerprint.json').read_text('utf8'));config=saved['inputs']['config'];fingerprint,_=input_fingerprint(a.input,config);assert fingerprint==saved['fingerprint'];state=run/'checkpoints'/f'state_{a.sample:06d}.npz';baseline=np.load(run/'positions.npy',mmap_mode='r');latest=json.loads((run/'latest_state.json').read_text('utf8'))['sample'];assert a.sample+a.steps<=latest;s=DynamicsSession(a.input,config);s.load(state,fingerprint);rows=[];started=time.monotonic()
for k in range(a.sample+1,a.sample+a.steps+1):
 metrics=s.advance(k);error=np.linalg.norm(s.solver.positions()-baseline[k],axis=1);row=dict(sample=k,max_position_error_m=float(error.max()),rms_position_error_m=float(np.sqrt(np.mean(error**2))),body_crossings=metrics['body_crossings']);rows.append(row)
passed=all(x['max_position_error_m']<1e-4 and x['rms_position_error_m']<1e-5 and x['body_crossings']==0 for x in rows)
report=dict(status='REAL_POSITION_VELOCITY_CHECKPOINT_REPLAY_PASS' if passed else 'REPLAY_DIFFERENCE_EXCEEDS_TOLERANCE',checkpoint=str(state),fingerprint=fingerprint,max_tolerance_m=1e-4,rms_tolerance_m=1e-5,bit_exact=False,floating_point_atomic_contact_accumulation=True,rows=rows,seconds=time.monotonic()-started);Path(a.out).write_text(json.dumps(report,indent=2),encoding='utf8');assert passed,report;print('CHECKPOINT_REPLAY_PASS',max(x['max_position_error_m'] for x in rows),flush=True)
