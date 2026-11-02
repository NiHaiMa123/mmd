"""Clean only the animated collision proxy within a measured sub-mm bound."""
import sys,json
from pathlib import Path
import numpy as np
source=Path(sys.argv[1]).resolve();out=source.parent/(source.name+'_clean');out.mkdir(exist_ok=True);data=dict(np.load(source/'trajectories.npz'));body=data['body'].astype(np.float64);faces=data['body_faces'];edges=np.unique(np.sort(np.concatenate((faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]])),axis=1),axis=0);length=np.linalg.norm(body[0,edges[:,0]]-body[0,edges[:,1]],axis=1);parent=list(range(body.shape[1]));members={i:[i] for i in parent}
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for a,b in edges[length<.0001]:
    ra,rb=root(int(a)),root(int(b))
    if ra==rb:continue
    selected=min(ra,rb);other=max(ra,rb);combined=members[ra]+members[rb]
    if np.linalg.norm(body[:,combined]-body[:,selected:selected+1],axis=2).max()<=.0001:
        parent[other]=selected;members[selected]=combined;members.pop(other)
labels=np.array([root(i) for i in range(len(parent))]);unique,inverse=np.unique(labels,return_inverse=True);clean=body[:,unique].copy();newfaces=inverse[faces];newfaces=newfaces[np.array([len(set(f))==3 for f in newfaces])];_,index=np.unique(np.sort(newfaces,axis=1),axis=0,return_index=True);newfaces=newfaces[np.sort(index)]
adjustments=np.zeros_like(clean[0]);remaining=0
for iteration in range(8):
    rest=clean[0]+adjustments;tri=rest[newfaces];mat=np.stack((tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=2);sv=np.linalg.svd(mat,compute_uv=False);ratio=sv[:,1]/np.maximum(sv[:,0],1e-16);bad=np.flatnonzero(ratio<.0005);remaining=len(bad)
    if not len(bad):break
    for fi in bad:
        f=newfaces[fi];p=rest[f];choices=[(np.linalg.norm(p[i]-p[j]),i,j,3-i-j) for i,j in ((0,1),(0,2),(1,2))];_,i,j,k=max(choices);axis=p[j]-p[i];axis/=np.linalg.norm(axis);height=p[k]-p[i]-axis*np.dot(p[k]-p[i],axis)
        if np.linalg.norm(height)<1e-12:height=np.cross(axis,[0,0,1] if abs(axis[2])<.8 else [0,1,0])
        height/=np.linalg.norm(height);adjustments[f[k]]+=height*.00008
        if np.linalg.norm(adjustments[f[k]])>.00025:raise RuntimeError('Collision proxy cleanup exceeded 0.25 mm vertex displacement')
if remaining:raise RuntimeError(f'{remaining} ill-conditioned proxy faces remain')
clean+=adjustments[None,:,:];delta=np.linalg.norm(clean[:,inverse]-body,axis=2).max();assert delta<.0004,delta
data['body']=clean.astype(np.float32);data['body_faces']=newfaces.astype(np.int32);np.savez_compressed(out/'trajectories.npz',**data);manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'));manifest['collision_proxy_cleanup']=dict(original_vertices=body.shape[1],vertices=clean.shape[1],original_faces=len(faces),faces=len(newfaces),max_surface_vertex_displacement_m=float(delta),visible_model_changed=False,min_rest_condition=float(ratio.min()));(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print('PPF_COLLIDER_CLEAN',manifest['collision_proxy_cleanup'],flush=True)
