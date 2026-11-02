"""Replay mature MMD bone physics on all original render hair vertices."""
import argparse,json,time
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();run=Path(a.run)
P=Path(r'E:\project\mmd\work\headswap_xl_codex');src=P/'fullhair_repro_20261030/input_body_aware'
j=json.loads((run/'bones.json').read_text('utf8'));names=j['names'];n=len(names)
m=np.memmap(run/'world_matrices.f32',dtype='<f4',mode='r',shape=(3833,n,4,4)).swapaxes(-1,-2)
initial=np.fromfile(run/'initial_world.f32',dtype='<f4').reshape(n,4,4).swapaxes(-1,-2).astype('f8')
binding=np.load(P/'fullhair_repro_20261030/review_11s_20261030/hair_binding.npz')
aliases=json.loads((P/'native_mmd_bridge_20261030/input/bone_name_map.json').read_text('utf8'));reverse={v:k for k,v in aliases.items()}
indices=np.asarray([names.index(reverse[x]) for x in binding['names'].tolist()]);weights=binding['weights'];top=np.argsort(weights,axis=1)[:,-4:];w=np.take_along_axis(weights,top,axis=1);assert np.max(abs(w.sum(1)-1))<1e-5
bi=indices[top];x0=np.load(src/'hair_initial.npy').astype('f8');anchors=np.load(src/'anchors.npy',mmap_mode='r')[:,-1];hard=np.load(src/'hard_roots.npy');edges=np.load(src/'hair_edges.npy');ref=np.load(src/'hair_original.npy');length=np.linalg.norm(ref[edges[:,0]]-ref[edges[:,1]],axis=1);valid=length>.0005
S=np.eye(4);S[:3,:3]=np.array([[1,0,0],[0,0,1],[0,1,0]])*.08;Sinv=np.linalg.inv(S)
initialSI=S@initial@Sinv;inverse=np.linalg.inv(initialSI);h=names.index('B0009');H0inv=np.linalg.inv(anchors[0]);N0inv=inverse[h]
assert not (run/'positions.npy').exists(),'Preserve existing trajectory'
positions=np.lib.format.open_memmap(run/'positions.npy',dtype='<f4',mode='w+',shape=(3593,len(x0),3));rows=[];started=time.monotonic()
for k in range(3593):
    native=S@m[k+240].astype('f8')@Sinv;D=native@inverse
    selected=D[bi];x=(np.einsum('nwij,nj->nwi',selected[:,:,:3,:3],x0)+selected[:,:,:3,3]);x=np.einsum('nw,nwi->ni',w,x)
    sr=anchors[k]@H0inv;nr=native[h]@N0inv;correction=sr@np.linalg.inv(nr);x=x@correction[:3,:3].T+correction[:3,3]
    expected=x0@sr[:3,:3].T+sr[:3,3];rooterror=float(np.linalg.norm(x[hard]-expected[hard],axis=1).max());assert rooterror<1e-5,rooterror;x[hard]=expected[hard]
    positions[k]=x
    if k%8==0:
        ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/length[valid]
        row=dict(frame=1+k/8,min_edge_ratio=float(ratio.min()),max_edge_ratio=float(ratio.max()),edge_p1=float(np.percentile(ratio,1)),edge_p99=float(np.percentile(ratio,99)),root_error_m=rooterror);rows.append(row)
        if k%240==0:print(json.dumps(row),flush=True)
positions.flush();(run/'mesh_replay.json').write_text(json.dumps(dict(stage='RAW_BONE_REPLAY_REQUIRES_CONTACT_AND_VISUAL_QA',samples=3593,vertices=len(x0),rows=rows,elapsed_s=time.monotonic()-started),indent=2),'utf8')
