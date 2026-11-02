"""Read-only triangle-pair padding audit using stock Cloth's pair rules.

This measures static distances; it does not implement collision response.
Rules checked against Blender 5.2 collision.cc: doubled self epsilon, shared
vertices excluded, both-fully-pinned pairs excluded, no extra one-ring skip.
"""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.geometry import closest_point_on_tri
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);candidate=Path(a.candidate)
c=json.loads((candidate/'configuration.json').read_text('utf8'));z=np.load(candidate/'clump_proxy_rest.npz')
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
h=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')['head_matrix']
x=z['vertices']@h[:3,:3].T+h[:3,3];tri=z['triangles'];pins=z['pins'].astype(bool)
scale=c.get('simulation_scale',1.);epsilon=c['self_collision_distance_m']
radius=2*epsilon;flt_epsilon=float(np.finfo(np.float32).eps)
def seg_dist2(a,b,c,d):
    u=b-a;v=d-c;w=a-c
    aa=u.dot(u);bb=u.dot(v);cc=v.dot(v);dd=u.dot(w);ee=v.dot(w)
    denom=aa*cc-bb*bb
    s=float(np.clip((bb*ee-cc*dd)/denom,0,1)) if abs(denom)>1e-30 else 0.
    t=(bb*s+ee)/cc
    if t<0:t=0.;s=float(np.clip(-dd/aa,0,1))
    elif t>1:t=1.;s=float(np.clip((bb-dd)/aa,0,1))
    q=w+s*u-t*v;return q.dot(q)
def distance(a,b):
    av=[Vector(v) for v in a];bv=[Vector(v) for v in b]
    minimum=min((v-closest_point_on_tri(v,*bv)).length_squared for v in av)
    minimum=min(minimum,min((v-closest_point_on_tri(v,*av)).length_squared for v in bv))
    for i in range(3):
        for j in range(3):minimum=min(minimum,seg_dist2(a[i],a[(i+1)%3],b[j],b[(j+1)%3]))
    return float(np.sqrt(max(minimum,0)))
started=time.monotonic();tested=0;violations=[];active=0;minimum=None
points=x[tri];centers=points.mean(1);radii=np.linalg.norm(points-centers[:,None,:],axis=2).max(1)
lower=points.min(1);upper=points.max(1);max_radius=float(radii.max())
tree=KDTree(len(tri))
for i,v in enumerate(centers):tree.insert(v,i)
tree.balance();candidates=0
for i in range(len(tri)):
    neighbors=tree.find_range(centers[i],radii[i]+max_radius+radius+1e-6)
    for _,j,center_distance in neighbors:
        if i>=j or center_distance>radii[i]+radii[j]+radius+1e-6:continue
        gap=np.maximum(np.maximum(lower[i]-upper[j],lower[j]-upper[i]),0.)
        if gap.dot(gap)>(radius+1e-6)**2:continue
        if set(tri[i]).intersection(tri[j]):continue
        if np.all(pins[tri[i]]) and np.all(pins[tri[j]]):continue
        candidates+=1;tested+=1;d=distance(points[i],points[j])
        if d<=radius+flt_epsilon/scale:
            is_active=bool((d*scale)**2>flt_epsilon)
            active+=int(is_active);violations.append(dict(triangles=[int(i),int(j)],distance_m=d,native_vector_threshold_pass=is_active))
            minimum=d if minimum is None else min(minimum,d)
    if i%5000==0:print(json.dumps(dict(triangle=i,total=len(tri),pairs_tested=tested,padding_overlaps=len(violations),elapsed_s=time.monotonic()-started)),flush=True)
report=dict(method='Static triangle-pair distances with native shared-vertex/pinning exclusions and doubled self epsilon',
    source_code='https://github.com/blender/blender/blob/blender-v5.2-release/source/blender/blenkernel/intern/collision.cc',
    scope='Pair selection and distance/envelope criteria reproduced; no native response or continuous-time proof',
    configured_self_epsilon_real_m=epsilon,native_pair_detection_distance_real_m=radius,
    native_response_target_distance_real_m=radius*8/9,simulation_scale=scale,
    broadphase='Centroid bounding spheres plus Euclidean AABB lower bound',
    tested_pairs=tested,padding_overlap_pairs=len(violations),native_active_initial_pairs=active,
    minimum_padding_pair_distance_m=minimum,witnesses=sorted(violations,key=lambda r:r['distance_m'])[:50],
    complete=True,elapsed_s=time.monotonic()-started,physics_started=False)
(candidate/'native_rest_padding_audit.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps(report),flush=True)
