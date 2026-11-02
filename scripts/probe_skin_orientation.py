import json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import inside_votes
path=Path(sys.argv[sys.argv.index('--')+1]);
with np.load(path/'surfaces_325.npz') as z:co=z['skin'].copy();faces=z['skin_faces'].copy()
tree=BVHTree.FromPolygons(co.tolist(),faces.tolist(),all_triangles=True);results=[]
for i in np.random.default_rng(731).choice(len(faces),120,replace=False):
    tri=co[faces[i]];n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);n/=np.linalg.norm(n);p=tri.mean(axis=0);results.append({'z':float(p[2]),'plus_inside':inside_votes(tree,Vector(p+n*.001)),'minus_inside':inside_votes(tree,Vector(p-n*.001))})
r={'plus_inside':sum(x['plus_inside'] for x in results),'minus_inside':sum(x['minus_inside'] for x in results),'samples':results,'signed_skin_volume':float(np.sum(np.einsum('ij,ij->i',co[faces[:,0]],np.cross(co[faces[:,1]],co[faces[:,2]])))/6)};(path/'orientation.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print({k:v for k,v in r.items() if k!='samples'},flush=True)
