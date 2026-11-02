import sys
from pathlib import Path
import numpy as np
import warp as wp
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector,strict_tri_intersects
@wp.kernel
def find_pairs(mesh:wp.uint64,body:wp.array(dtype=wp.vec3),bf:wp.array(dtype=wp.vec3i),flags:wp.array(dtype=int),x:wp.array(dtype=wp.vec3),hf:wp.array(dtype=wp.vec3i),out:wp.array(dtype=wp.vec2i),counter:wp.array(dtype=int)):
 i=wp.tid();f=hf[i];a=x[f[0]];b=x[f[1]];c=x[f[2]];q=wp.mesh_query_aabb(mesh,wp.min(wp.min(a,b),c),wp.max(wp.max(a,b),c));k=int(0)
 while wp.mesh_query_aabb_next(q,k):
  f2=bf[k]
  if flags[k]>0 and strict_tri_intersects(a,b,c,body[f2[0]],body[f2[1]],body[f2[2]])>0:
   index=wp.atomic_add(counter,0,1)
   if index<100000:out[index]=wp.vec2i(i,k)
src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input';initial=np.load(src/'hair_initial.npy');edges=np.load(src/'hair_edges.npy');faces=np.load(src/'hair_faces.npy');body=np.load(src/'body.npy',mmap_mode='r');bf=np.load(src/'body_faces.npy');solver=SurfaceProjector(initial,edges,faces,body[0],bf,body_real_faces=np.load(src/'real_body_faces.npy'));out=wp.zeros(100000,dtype=wp.vec2i,device='cuda:0');counter=wp.zeros(1,dtype=int,device='cuda:0');wp.launch(find_pairs,len(faces),inputs=[solver.mesh.id,solver.body,solver.bodyfaces,solver.body_real_faces,solver.x,solver.faces,out,counter],device='cuda:0');n=int(counter.numpy()[0]);np.save(src.parent/'gpu_initial_intersection_pairs.npy',out.numpy()[:min(n,100000)]);print('INITIAL_GPU_STRICT_PAIRS',n,flush=True)
