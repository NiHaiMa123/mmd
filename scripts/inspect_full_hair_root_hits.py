import argparse,json,sys
from pathlib import Path
from collections import Counter
import numpy as np
import warp as wp
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
@wp.kernel
def query_faces(mesh:wp.uint64,points:wp.array(dtype=wp.vec3),faces:wp.array(dtype=int)):
 i=wp.tid();q=wp.mesh_query_point_sign_winding_number(mesh,points[i],100.0);faces[i]=q.face
src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input';x=np.load(src/'hair_initial.npy');body=np.load(src/'body.npy',mmap_mode='r');heads=np.load(src/'anchors.npy',mmap_mode='r');weights=np.load(src/'anchor_weights.npy');hard=np.load(src/'hard_roots.npy');w=weights.copy();w[:,-1]+=np.maximum(1-w.sum(1),0);w/=w.sum(1)[:,None];inv=np.linalg.inv(heads[0]);local=np.einsum('bij,vj->bvi',inv[:,:3,:3],x)+inv[:,None,:3,3];solver=SurfaceProjector(x,np.load(src/'hair_edges.npy'),np.load(src/'hair_faces.npy'),body[0],np.load(src/'body_faces.npy'));labels=np.load(src/'body_face_role.npy');names=json.loads((src/'body_role_names.json').read_text('utf8'));rows=[]
for frame in [210,218,225,234.25,235.25,242,248,254.25]:
 k=round((frame-1)*4);target=sum((local[b]@heads[k,b,:3,:3].T+heads[k,b,:3,3])*w[:,b,None] for b in range(2));solver.body_update(body[k]);d,_=solver.distances(target[hard]);points=wp.array(target[hard],dtype=wp.vec3,device='cuda:0');faces=wp.zeros(len(points),dtype=int,device='cuda:0');wp.launch(query_faces,len(points),inputs=[solver.mesh.id,points,faces],device='cuda:0');hits=faces.numpy()[d<-.0001];row=dict(frame=frame,roles=dict(Counter(names[labels[i]] for i in hits)),minimum=float(d.min()));rows.append(row);print('ROOT_HIT_ROLES',row,flush=True)
(src.parent/'root_hit_roles.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
