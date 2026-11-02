"""Standard selected MeshLab isotropic remeshing of a static proxy patch.

No dynamics, contact response or per-frame correction. Original displayed hair
and the entire authored fixed-root set are read-only.
"""
import argparse,json,hashlib,importlib.metadata
from pathlib import Path
import numpy as np,igl,pymeshlab
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
p.add_argument('--operation-deviation',type=float,default=.00004)
p.add_argument('--deviation-budget',type=float,default=.0002)
p.add_argument('--iterations',type=int,default=3)
p.add_argument('--feature-angle',type=float,default=180.)
p.add_argument('--padding-audit',help='Static native padding witnesses for a local quality repair, never animation frames')
a=p.parse_args();source=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'clump_proxy_rest.npz').exists(),'Use a fresh static asset directory'
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
z=np.load(source/'clump_proxy_rest.npz');v=z['vertices'];f=z['triangles'];oldpins=z['pins'].astype(bool)
inp=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');inv=np.linalg.inv(inp['head_matrix'])
points=inp['world']@inv[:3,:3].T+inv[:3,3]
exp=base/'fullhair_repro_20261030/input_body_aware';body=np.load(exp/'body.npy',mmap_mode='r')[0]
body=body@inv[:3,:3].T+inv[:3,3];bf=np.load(exp/'body_faces.npy')[np.load(exp/'real_body_faces.npy').astype(bool)]
skin_distance=np.sqrt(igl.point_mesh_squared_distance(v.astype(float),body.astype(float),bf.astype(np.int64))[0])
near=cKDTree(points[inp['chain_labels']==0]).query(v)[0]<.018
far=cKDTree(points[inp['hard'].astype(bool)]).query(v)[0]>.02
selected=np.all((near&far&(skin_distance<.02))[f],axis=1)
if a.padding_audit:
    padding=json.loads(Path(a.padding_audit).read_text('utf8'))
    assert padding['complete'] and len(padding['witnesses'])==padding['padding_overlap_pairs'],'Require complete static witness set'
    selected=np.zeros(len(f),bool)
    selected[np.unique([i for row in padding['witnesses'] for i in row['triangles']])]=True
    for _ in range(2):
        marked=np.zeros(len(v),bool);marked[f[selected].ravel()]=True
        selected|=np.any(marked[f],axis=1)
    selected&=np.all(far[f],axis=1)&~np.any(oldpins[f],axis=1)
ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(v.astype(float),f.astype(np.int32),f_scalar_array=selected.astype(float)))
ms.compute_selection_by_condition_per_face(condselect='fq > 0.5')
assert ms.current_mesh().selected_face_number()==int(selected.sum()),'MeshLab selected-face interface mismatch'
params=dict(iterations=a.iterations,selectedonly=True,target_length_m=.0015,max_surface_distance_m=a.operation_deviation,
    feature_angle_degrees=a.feature_angle,adaptive=False,reproject=True)
ms.meshing_isotropic_explicit_remeshing(iterations=a.iterations,adaptive=False,selectedonly=True,
    targetlen=pymeshlab.PureValue(.0015),featuredeg=a.feature_angle,checksurfdist=True,
    maxsurfdist=pymeshlab.PureValue(a.operation_deviation),splitflag=True,collapseflag=True,
    swapflag=True,smoothflag=True,reprojectflag=True)
nv=ms.current_mesh().vertex_matrix().copy();nf=ms.current_mesh().face_matrix().copy()
tree=cKDTree(nv);rd,ri=tree.query(v[oldpins]);root_error=float(rd.max())
assert root_error<1e-7 and len(np.unique(ri))==int(oldpins.sum()),'Static remesh changed original fixed roots'
pins=np.zeros(len(nv),bool);pins[ri]=True
edges,counts=np.unique(np.sort(np.concatenate([nf[:,[0,1]],nf[:,[1,2]],nf[:,[2,0]]]),axis=1),axis=0,return_counts=True)
graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(len(nv),len(nv)))
ncomp,labels=connected_components(graph,directed=False)
d1=igl.point_mesh_squared_distance(nv.astype(float),v.astype(float),f.astype(np.int64))[0]
d2=igl.point_mesh_squared_distance(v.astype(float),nv.astype(float),nf.astype(np.int64))[0]
deviation=float(np.sqrt(max(d1.max(),d2.max())))
report=dict(method='Installed MeshLab selected isotropic explicit remeshing',source=str(source),
    static_padding_audit=a.padding_audit,
    selected_faces=int(selected.sum()),parameters=params,vertices_before=len(v),vertices_after=len(nv),
    triangles_before=len(f),triangles_after=len(nf),fixed_root_count=int(pins.sum()),fixed_root_error_m=root_error,
    symmetric_vertex_surface_deviation_max_m=deviation,boundary_edges=int((counts==1).sum()),
    nonmanifold_edges=int((counts>2).sum()),components=ncomp,physics_started=False,render_hair_modified=False,
    versions={name:importlib.metadata.version(name) for name in ['pymeshlab','libigl','numpy']},
    source_sha256=hashlib.sha256((source/'clump_proxy_rest.npz').read_bytes()).hexdigest())
report['symmetric_deviation_budget_m']=a.deviation_budget
report['asset_gate_pass']=bool(ncomp==1 and np.all(counts==2) and deviation<=a.deviation_budget)
(out/'remesh_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
assert report['asset_gate_pass'],'Static remesher exceeded topology/deviation limits; do not bind'
arrays={k:z[k] for k in z.files};nearest=cKDTree(v).query(nv)[1]
arrays.update(vertices=nv,triangles=nf.astype(np.int32),pins=pins,clump_ids=z['clump_ids'][nearest],component_ids=labels)
np.savez_compressed(out/'clump_proxy_rest.npz',**arrays)
topology=dict(raw_vertices=len(v),vertices=len(nv),triangles=len(nf),components=[dict(vertices=len(nv),rooted=True)],
    pins=int(pins.sum()),deleted_components=0,all_27_groups_tracked=True,physical_clump_splits=False,
    manifold_clean_asset=True,post_import_simplification=False,standard_selected_static_remesh=report)
(out/'geometric_topology.json').write_text(json.dumps(topology,ensure_ascii=False,indent=2),'utf8')
