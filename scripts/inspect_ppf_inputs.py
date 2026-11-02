import json,sys
from pathlib import Path
from collections import Counter
import numpy as np
p=Path(sys.argv[1]);report={}
# NPZ entries decompress on every access. Cache once before per-face loops.
with np.load(p/'trajectories.npz') as archive:data={key:archive[key] for key in archive.files}
for name in ('cloth','body'):
    faces=data[name+'_faces'];co=data[name][0]
    report[name]=dict(vertices=len(co),triangles=len(faces),duplicate_faces=len(faces)-len(np.unique(np.sort(faces,axis=1),axis=0)),zero_area=int(np.sum(np.linalg.norm(np.cross(co[faces[:,1]]-co[faces[:,0]],co[faces[:,2]]-co[faces[:,0]]),axis=1)<1e-10)))
key=lambda tri:tuple(sorted(tuple(np.rint(np.asarray(v,dtype=float)*1e6).astype(int)) for v in tri))
lookup={key(data[n][0][f]):(n,tuple(f)) for n in ('cloth','body') for f in data[n+'_faces']}
parent=list(range(len(data['cloth'][0])))
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in data['cloth_faces']:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
labels={r:i for i,r in enumerate(sorted({root(i) for i in parent}))};component={i:labels[root(i)] for i in range(len(parent))}
report['cloth_components']={str(c):dict(vertices=sum(v==c for v in component.values()),bounds=[data['cloth'][0][[i for i,v in component.items() if v==c]].min(axis=0).tolist(),data['cloth'][0][[i for i,v in component.items() if v==c]].max(axis=0).tolist()]) for c in labels.values()}
status=json.loads((p/'solve_status.json').read_text());pairs=Counter();shared=Counter();component_pairs=Counter();collider_components=Counter();centroids=[]
for v in status.get('violations',[]):
    for pair in v.get('tris',[]):
        if len(pair)!=2:continue
        a,b=[lookup.get(key(t),('unknown',())) for t in pair];pairs[(a[0],b[0])]+=1
        if a[0]==b[0]:shared[(a[0],len(set(a[1])&set(b[1])))]+=1
        if a[0]==b[0]=='cloth':component_pairs[(component[a[1][0]],component[b[1][0]])]+=1
        if {a[0],b[0]}=={'cloth','body'}:
            cloth=a if a[0]=='cloth' else b;collider_components[component[cloth[1][0]]]+=1;centroids.append(np.asarray(pair,dtype=float).mean(axis=(0,1)))
report['reported_pair_sample']={str(k):v for k,v in pairs.items()};report['shared_vertices_of_reported_pairs']={str(k):v for k,v in shared.items()}
report['component_pairs']={str(k):v for k,v in component_pairs.items()}
report['cloth_collider_components']={str(k):v for k,v in collider_components.items()}
if centroids:report['cloth_collider_contact_centroid_bounds_m']=[np.min(centroids,axis=0).tolist(),np.max(centroids,axis=0).tolist()]
(p/'input_diagnostics.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
