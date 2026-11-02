"""Read-only geometry verification plus updated metadata after static asset fit."""
import argparse,json
from pathlib import Path
import numpy as np,igl
from scipy.spatial import cKDTree
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args();out=Path(a.candidate)
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
source=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');z=np.load(out/'clump_proxy_rest.npz')
c=json.loads((out/'configuration.json').read_text('utf8'));inv=np.linalg.inv(source['head_matrix'])
points=source['world']@inv[:3,:3].T+inv[:3,3]
v=z['vertices'].astype(np.float64);f=z['triangles'].astype(np.int64)
w=igl.fast_winding_number(v,f,points.astype(np.float64));d,_,closest=igl.point_mesh_squared_distance(points.astype(np.float64),v,f)
dist=np.sqrt(d);inside=w>.5;labels=source['chain_labels']
root_dist=cKDTree(points[source['hard'].astype(bool)]).query(v[z['pins'].astype(bool)])[0]
clumps=[]
for ci,r in enumerate(c['clumps']):
    sel=labels==ci;outside=~inside[sel];ds=dist[sel];od=ds[outside]
    r.update(nearest_surface_p95_m=float(np.quantile(ds,.95)),nearest_surface_max_m=float(ds.max()),
        inside_cage_vertices=int((~outside).sum()),outside_cage_vertices=int(outside.sum()),
        outside_surface_distance_max_m=float(od.max()) if len(od) else 0.,
        root_pin_max_distance_to_authored_root_set_m=float(root_dist.max()),
        coverage_pass=bool(not len(od) or od.max()<=.008))
    clumps.append(r)
report=dict(all_27_groups_checked=len(clumps)==27,coverage_failures=[r['name'] for r in clumps if not r['coverage_pass']],
    maximum_root_pin_distance_m=float(root_dist.max()),nonmanifold_vertex_count=int((~igl.is_vertex_manifold(f)).sum()),
    render_geometry_modified=False,physics_started=False)
previous=json.loads((base/'standard_proxy_20261031/scale14_dynamic/reopened_frozen_audit/surface_audit.json').read_text('utf8'))
fail=next(r for r in previous['rows'] if r['frame']==13);ids=np.unique([i for r in fail['witnesses'] for i in r['hair_vertices']])
ix=np.searchsorted(source['ids'],ids)
exp=base/'fullhair_repro_20261030/input_body_aware';body=np.load(exp/'body.npy',mmap_mode='r')[0]
body=body@inv[:3,:3].T+inv[:3,3];bf=np.load(exp/'body_faces.npy')[np.load(exp/'real_body_faces.npy').astype(bool)].astype(np.int64)
_,bfi,_=igl.point_mesh_squared_distance(points[ix].astype(np.float64),body.astype(np.float64),bf)
normals=np.cross(body[bf[bfi,1]]-body[bf[bfi,0]],body[bf[bfi,2]]-body[bf[bfi,0]])
normals/=np.linalg.norm(normals,axis=1)[:,None]
offset=np.einsum('ij,ij->i',points[ix]-closest[ix],normals)
report.update(previous_failure_source_ids=ids.tolist(),previous_failure_rest_proxy_distance_mm=(dist[ix]*1000).tolist(),
    previous_failure_rest_outward_offset_mm=(offset*1000).tolist(),
    offset_note='Signed normal component from nearest proxy point toward original display point; static diagnostic, not a bound on native Surface Deform response')
c.update(clumps=clumps,clumps_with_coverage_failure=report['coverage_failures'],
    root_attachment_review_failures=[r['name'] for r in clumps if r['root_pin_max_distance_to_authored_root_set_m']>.015],
    updated_static_coverage_report=str(out/'static_coverage.json'))
(out/'configuration.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),'utf8')
(out/'clump_assets.json').write_text(json.dumps(clumps,ensure_ascii=False,indent=2),'utf8')
(out/'static_coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
