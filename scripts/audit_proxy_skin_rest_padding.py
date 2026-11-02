"""Read-only exact triangle distance check for initial proxy/actual skin padding.

No mesh editing, contact response or physics. Actual surface intersections are
checked separately; a triangle piercing another triangle is not inferred from
vertex distances. This check covers all triangles, including fixed patches.
"""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.geometry import closest_point_on_tri
from mathutils.kdtree import KDTree
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.candidate)
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
c=json.loads((out/'configuration.json').read_text('utf8'));z=np.load(out/'clump_proxy_rest.npz')
h=np.load(base/'standard_proxy_20261031/inspection/inputs.npz')['head_matrix']
x=z['vertices']@h[:3,:3].T+h[:3,3];pf=z['triangles'];pins=z['pins'].astype(bool)
exp=base/'fullhair_repro_20261030/input_body_aware'
y=np.load(exp/'body.npy',mmap_mode='r')[0]
bf=np.load(exp/'body_faces.npy')[np.load(exp/'real_body_faces.npy').astype(bool)]
margin=c['cloth_collision_distance_m']+c['body_collision_outer_m']
def segment_distance2(a,b,c,d):
    u=b-a;v=d-c;w=a-c
    aa=u.dot(u);bb=u.dot(v);cc=v.dot(v);dd=u.dot(w);ee=v.dot(w)
    if aa<1e-30 or cc<1e-30:raise ValueError('Degenerate triangle edge in padding audit')
    denom=aa*cc-bb*bb
    s=float(np.clip((bb*ee-cc*dd)/denom,0,1)) if abs(denom)>1e-30 else 0.
    t=(bb*s+ee)/cc
    if t<0:t=0.;s=float(np.clip(-dd/aa,0,1))
    elif t>1:t=1.;s=float(np.clip((bb-dd)/aa,0,1))
    q=w+s*u-t*v;return q.dot(q)
def distance(a,b):
    av=[Vector(v) for v in a];bv=[Vector(v) for v in b]
    d2=min((v-closest_point_on_tri(v,*bv)).length_squared for v in av)
    d2=min(d2,min((v-closest_point_on_tri(v,*av)).length_squared for v in bv))
    for i in range(3):
        for j in range(3):d2=min(d2,segment_distance2(a[i],a[(i+1)%3],b[j],b[(j+1)%3]))
    return float(np.sqrt(max(d2,0.)))
start=time.monotonic();points=x[pf];skin=y[bf]
pc=points.mean(1);sc=skin.mean(1)
pr=np.linalg.norm(points-pc[:,None,:],axis=2).max(1)
sr=np.linalg.norm(skin-sc[:,None,:],axis=2).max(1)
pl,pu=points.min(1),points.max(1);sl,su=skin.min(1),skin.max(1)
tree=KDTree(len(bf))
for i,v in enumerate(sc):tree.insert(v,i)
tree.balance();max_radius=float(sr.max());tested=0;violations=[]
tolerance=float(np.finfo(np.float32).eps)/c.get('simulation_scale',1.)
for i in range(len(pf)):
    for _,j,cd in tree.find_range(pc[i],pr[i]+max_radius+margin+1e-6):
        if cd>pr[i]+sr[j]+margin+1e-6:continue
        gap=np.maximum(np.maximum(pl[i]-su[j],sl[j]-pu[i]),0.)
        if gap.dot(gap)>(margin+1e-6)**2:continue
        tested+=1;d=distance(points[i],skin[j])
        if d<margin+tolerance:
            violations.append(dict(proxy_triangle=i,skin_triangle=j,distance_m=d,
                all_proxy_vertices_fixed=bool(pins[pf[i]].all())))
    if i%10000==0:print(json.dumps(dict(triangle=i,total=len(pf),tested_pairs=tested,
        padding_overlaps=len(violations),elapsed_s=time.monotonic()-start)),flush=True)
report=dict(method='Complete initial triangle-pair padding search; six vertex/face and nine edge/edge distances',
    actual_intersections_checked_separately=True,configured_combined_body_margin_m=margin,
    broadphase='Centroid bounding spheres plus Euclidean AABB lower bound',
    tested_pairs=tested,padding_overlap_pairs=len(violations),complete=True,
    minimum_violating_pair_distance_m=min((r['distance_m'] for r in violations),default=None),
    witnesses=sorted(violations,key=lambda r:r['distance_m'])[:50],
    physics_started=False,elapsed_s=time.monotonic()-start)
(out/'proxy_skin_rest_padding_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
