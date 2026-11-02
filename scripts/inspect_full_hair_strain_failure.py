import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
import warp as wp
from mmd_hair_dynamics.dynamics import DynamicsSession
from mmd_hair_dynamics.gpu_surface import query_details
src=Path(sys.argv[1]);s=DynamicsSession(src);z=np.load(sys.argv[2]);k=int(z['index']);x=z['positions'];s.solver.x.assign(x);s.solver.body_update(s.body[k]);e=s.edges;old=s.solver.rest;l=np.linalg.norm(old[e[:,0]]-old[e[:,1]],axis=1);ratio=np.linalg.norm(x[e[:,0]]-x[e[:,1]],axis=1)/np.maximum(l,1e-10);select=np.flatnonzero(l>.0005);bad=select[np.argsort(ratio[select])[-10:]];ids=np.unique(e[bad].ravel());points=wp.array(x[ids],dtype=wp.vec3,device='cuda:0');n=len(ids);d=wp.empty(n,dtype=float,device='cuda:0');normal=wp.empty(n,dtype=wp.vec3,device='cuda:0');face=wp.empty(n,dtype=int,device='cuda:0');bary=wp.empty(n,dtype=wp.vec3,device='cuda:0');wp.launch(query_details,n,inputs=[s.solver.mesh.id,points,d,normal,face,bary],device='cuda:0');roles=np.load(src.parent/'input/body_face_role.npy');names=json.loads((src.parent/'input/body_role_names.json').read_text('utf8'));details={int(i):dict(source_id=int(np.load(src/'hair_ids.npy')[i]),hard=bool(s.hard[i]),position=x[i].tolist(),distance_m=float(dd),body_role=names[roles[ff]]) for i,dd,ff in zip(ids,d.numpy(),face.numpy())};r=dict(sample=k,frame=1+k*.125,edges=[dict(ids=e[i].tolist(),ratio=float(ratio[i]),source_length_m=float(l[i]),vertices=[details[int(j)] for j in e[i]]) for i in bad]);print(json.dumps(r,ensure_ascii=False,indent=2),flush=True)
