"""Use the verified rest envelope at the short clip start, not an old simulation."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a fresh rest-envelope directory')
with np.load(src/'trajectories.npz') as z:d={k:z[k] for k in z.files}
manifest=json.loads((src/'manifest.json').read_text('utf8'));run=Path(manifest['source_run']);r=json.loads((run/'report.json').read_text('utf8'))
with np.load(run/'native_integer.npz') as z:rest=z['proxy_coordinates'][0]
with np.load(run/'dense_motion.npz') as z:heads=z['anchor_matrices']
first,last=manifest['source_frames'];times=np.asarray(manifest['sample_times_s']);frames=first+times*manifest['fps'];indices=(frames-r['frames'][0])/r['step_frames']
if np.max(np.abs(indices-np.rint(indices)))>1e-6:raise ValueError('Source head cache must include exact target times')
deltas=heads[np.rint(indices).astype(int)]@np.linalg.inv(heads[0]);d['cloth']=np.einsum('fij,vj->fvi',deltas[:,:3,:3],rest)+deltas[:,None,:3,3];np.savez_compressed(out/'trajectories.npz',**d);manifest['proxy_initialization']='verified clean rest envelope, rigidly transported by the exact source head; body trajectories unchanged';(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('REST_PROXY_RESET',len(frames),len(rest),flush=True)
