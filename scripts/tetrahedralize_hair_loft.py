"""Fill the known parallel-slice loft with conforming tetrahedral prisms."""
import argparse,json
from pathlib import Path
from collections import Counter
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a fresh volume directory')
with np.load(src/'trajectories.npz') as archive:d={k:archive[k] for k in archive.files}
manifest=json.loads((src/'manifest.json').read_text('utf8'));setup=json.loads((Path(manifest['source_run'])/'setup.json').read_text('utf8'));rings=setup['proxy']['rings'];sides=setup['proxy']['sides'];boundary_count=rings*sides+2
if d['cloth'].shape[1]!=boundary_count:raise ValueError('Expected the verified ordered slice loft')
centers={0:rings*sides,rings-1:rings*sides+1};extra=[]
for k in range(1,rings-1):centers[k]=boundary_count+len(extra);extra.append(d['cloth'][:,k*sides:(k+1)*sides].mean(1))
vertices=np.concatenate((d['cloth'],np.stack(extra,axis=1)),axis=1);tets=[]
for k in range(rings-1):
 for j in range(sides):
  old=[centers[k],k*sides+j,k*sides+(j+1)%sides];new=[centers[k+1],(k+1)*sides+j,(k+1)*sides+(j+1)%sides];order=np.argsort(old);aa,bb,cc=np.array(old)[order];AA,BB,CC=np.array(new)[order];tets.extend([(aa,bb,cc,CC),(aa,bb,BB,CC),(aa,AA,BB,CC)])
tets=np.array(tets);points=vertices[0][tets];det=np.linalg.det(np.stack((points[:,1]-points[:,0],points[:,2]-points[:,0],points[:,3]-points[:,0]),axis=2));negative=det<0;tets[negative,0],tets[negative,1]=tets[negative,1].copy(),tets[negative,0].copy()
if np.min(np.abs(det))<1e-12:raise ValueError('Degenerate physical tetrahedron')
surface={}
for aa,bb,cc,dd in tets:
 for face in [(bb,cc,dd),(aa,dd,cc),(aa,bb,dd),(aa,cc,bb)]:surface.setdefault(tuple(sorted(face)),[]).append(face)
if any(len(f)>2 for f in surface.values()):raise ValueError('Nonmanifold tetrahedral adjacency')
faces=np.array([f[0] for f in surface.values() if len(f)==1]);edges=Counter(tuple(sorted((int(aa),int(bb)))) for f in faces for aa,bb in zip(f,np.roll(f,-1)))
if len(faces)!=len(d['cloth_faces']) or any(v!=2 for v in edges.values()):raise ValueError('Volume boundary does not match the closed loft')
d['cloth']=vertices;d['cloth_faces']=faces;d['tetrahedra']=tets;d['pins']=np.r_[d['pins'],np.zeros(len(extra))];d['original_mapping']=np.arange(boundary_count);np.savez_compressed(out/'trajectories.npz',**d);receipt=dict(method='conforming three-tet triangular prisms with ordered edge diagonals',vertices=vertices.shape[1],tetrahedra=len(tets),boundary_triangles=len(faces),minimum_rest_volume_m3=float(np.min(np.abs(det))/6),boundary_output_vertices=boundary_count,original_model_modified=False);manifest['volume_proxy']=receipt;(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_VOLUME',json.dumps(receipt),flush=True)
