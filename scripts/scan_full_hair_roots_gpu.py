import argparse,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--positions');a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);x=np.load(a.positions or src/'hair_initial.npy');edges=np.load(src/'hair_edges.npy');faces=np.load(src/'hair_faces.npy');body=np.load(src/'body.npy',mmap_mode='r');heads=np.load(src/'anchors.npy',mmap_mode='r');weights=np.load(src/'anchor_weights.npy');hard=np.load(src/'hard_roots.npy');ids=np.load(src/'hair_ids.npy');w=weights.copy();w[:,-1]+=np.maximum(1-w.sum(1),0);w/=w.sum(1)[:,None];inverse=np.linalg.inv(heads[0]);local=np.einsum('bij,vj->bvi',inverse[:,:3,:3],x)+inverse[:,None,:3,3];solver=SurfaceProjector(x,edges,faces,body[0],np.load(src/'body_faces.npy'),hard=hard,body_real_faces=np.load(src/'real_body_faces.npy'));start=time.monotonic();rows=[]
manifest=json.loads((src/'export_complete.json').read_text('utf8'));first=manifest['frames'][0];step=manifest['sample_step']
for k,matrices in enumerate(heads):
 target=np.zeros_like(x)
 for b in range(len(matrices)):target+=(local[b]@matrices[b,:3,:3].T+matrices[b,:3,3])*w[:,b,None]
 solver.body_update(body[k]);dist,_=solver.distances(target[hard]);inside=np.flatnonzero(dist<-.0001)
 if len(inside):rows.append(dict(frame=first+k*step,inside_roots=len(inside),min_distance_m=float(dist.min()),source_ids=ids[hard][inside].tolist()))
 if k%120==0:print('ROOT_SCAN',k,first+k*step,'failed',len(rows),flush=True)
report=dict(status='ROOT_FEEDBACK_REQUIRED' if rows else 'SAMPLED_ROOT_POINTS_CLEAR',samples=len(body),failed_samples=len(rows),failures=rows,seconds=time.monotonic()-start,root_set_unchanged=True);(out/'root_scan.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('ROOT_SCAN_COMPLETE',len(rows),report['seconds'],flush=True)
