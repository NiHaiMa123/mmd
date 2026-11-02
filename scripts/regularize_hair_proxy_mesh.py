"""Static mesh quality pass using the installed standard MeshLab remesher.

No animation solver, motion correction, collision response or frame edits.
"""
import argparse,json,time,hashlib,importlib.metadata
from pathlib import Path
import numpy as np
import pymeshlab,igl
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
p.add_argument('--method',choices=['isotropic','shortest-edge','local-relax'],default='isotropic')
a=p.parse_args();source=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
assert not (out/'geometric_volume.npz').exists(),'Use a new static asset directory'
start=time.monotonic()
def emit(stage,**kw):
    r=dict(stage=stage,elapsed_s=time.monotonic()-start,**kw)
    (out/'status.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps(r),flush=True)
def quality(v,f):
    e=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    lengths=np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1)
    t=v[f];sides=np.linalg.norm(np.roll(t,-1,axis=1)-t,axis=2)
    cosine=(np.roll(sides,1,axis=1)**2+sides**2-np.roll(sides,-1,axis=1)**2)/(2*np.roll(sides,1,axis=1)*sides)
    angles=np.rad2deg(np.arccos(np.clip(cosine,-1,1)))
    _,count=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0,return_counts=True)
    graph=coo_matrix((np.ones(len(e)),(e[:,0],e[:,1])),shape=(len(v),len(v)))
    n,_=connected_components(graph,directed=False)
    return dict(vertices=len(v),triangles=len(f),edge_min_m=float(lengths.min()),
        edge_quantiles_m=np.quantile(lengths,[.001,.01,.05,.5,.99]).tolist(),
        edges_below_2mm=int((lengths<.002).sum()),minimum_angle_deg=float(angles.min()),
        faces_below_15deg=int((angles.min(1)<15).sum()),boundary_edges=int((count==1).sum()),
        nonmanifold_edges=int((count>2).sum()),components=n)
z=np.load(source/'geometric_volume.npz');v=z['vertices'];f=z['triangles'];before=quality(v,f)
emit('STANDARD_MESHLAB_REMESH',before=before)
if a.method=='isotropic':
    ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(v.astype(float),f.astype(np.int32)))
    params=dict(iterations=10,adaptive=False,targetlen_m=.007,featuredeg=180.,
        checksurfdist=True,maxsurfdist_m=.001,reprojectflag=False)
    ms.meshing_isotropic_explicit_remeshing(iterations=params['iterations'],adaptive=False,
        targetlen=pymeshlab.PureValue(params['targetlen_m']),featuredeg=params['featuredeg'],
        checksurfdist=True,maxsurfdist=pymeshlab.PureValue(params['maxsurfdist_m']),
        splitflag=True,collapseflag=True,swapflag=True,smoothflag=True,reprojectflag=False)
    newv=ms.current_mesh().vertex_matrix().copy();newf=ms.current_mesh().face_matrix().copy()
    method='Installed MeshLab isotropic explicit remeshing; 180 degree feature threshold; no reprojection'
else:
    newv=v.astype(np.float64).copy();newf=f.astype(np.int32).copy();history=[]
    selection_count=0;relax_displacement=0.
    if a.method=='local-relax':
        e=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
        short=np.linalg.norm(v[e[:,0]]-v[e[:,1]],axis=1)<.002
        t=v[f];sides=np.linalg.norm(np.roll(t,-1,axis=1)-t,axis=2)
        cosine=(np.roll(sides,1,axis=1)**2+sides**2-np.roll(sides,-1,axis=1)**2)/(2*np.roll(sides,1,axis=1)*sides)
        bad_faces=np.rad2deg(np.arccos(np.clip(cosine,-1,1))).min(1)<15.
        selected=np.zeros(len(v),bool);selected[e[short].ravel()]=True;selected[f[bad_faces].ravel()]=True
        selected[f[np.any(selected[f],axis=1)].ravel()]=True
        selection_count=int(selected.sum())
        ms=pymeshlab.MeshSet();ms.add_mesh(pymeshlab.Mesh(v.astype(float),f.astype(np.int32),v_scalar_array=selected.astype(float)))
        ms.compute_selection_by_condition_per_vertex(condselect='q > 0.5')
        ms.apply_coord_taubin_smoothing(lambda_=.5,mu=-.53,stepsmoothnum=2,selected=True)
        newv=ms.current_mesh().vertex_matrix().copy();newf=ms.current_mesh().face_matrix().copy()
        relax_displacement=float(np.linalg.norm(newv-v,axis=1).max())
        emit('STANDARD_SELECTED_TAUBIN_RELAXATION',selected_vertices=selection_count,maximum_displacement_m=relax_displacement)
    previous=before
    for iteration in range(6):
        short=previous['edges_below_2mm']
        if short==0:break
        desired_faces=len(newf)-2*short
        newv,newf,_,_=igl.decimate(np.asfortranarray(newv,dtype=np.float64),
            np.asfortranarray(newf,dtype=np.int32),desired_faces,True)
        current=quality(newv,newf);history.append(current)
        emit('STANDARD_LIBIGL_SHORTEST_EDGE_COLLAPSE',iteration=iteration+1,quality=current)
        if current['edges_below_2mm']>=previous['edges_below_2mm']:break
        previous=current
    params=dict(minimum_edge_m=.002,block_intersections=True,placement='Edge midpoint',history=history,
        local_taubin_iterations=2 if a.method=='local-relax' else 0,selected_vertices=selection_count,
        relaxation_max_displacement_m=relax_displacement)
    method='Installed libigl shortest-edge collapse with intersection blocking; no global smoothing'
    if a.method=='local-relax':method='Standard selected MeshLab Taubin smoothing, then libigl intersection-blocking shortest-edge collapse'
after=quality(newv,newf)
d1,_,_=igl.point_mesh_squared_distance(newv.astype(np.float64),v.astype(np.float64),f.astype(np.int64))
d2,_,_=igl.point_mesh_squared_distance(v.astype(np.float64),newv.astype(np.float64),newf.astype(np.int64))
deviation=float(np.sqrt(max(d1.max(),d2.max())))
base=Path(__file__).resolve().parents[2]/'work/headswap_xl_codex'
inp=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');inv=np.linalg.inv(inp['head_matrix'])
points=inp['world']@inv[:3,:3].T+inv[:3,3]
winding=igl.fast_winding_number(newv.astype(np.float64),newf.astype(np.int64),points.astype(np.float64))
d,_,_=igl.point_mesh_squared_distance(points.astype(np.float64),newv.astype(np.float64),newf.astype(np.int64))
np.savez_compressed(out/'source_cage_coverage.npz',inside=winding>.5,distances=np.sqrt(d),winding=winding,source_vertex_ids=inp['ids'])
np.savez_compressed(out/'geometric_volume.npz',vertices=newv,triangles=newf,
    source_vertex_ids=z['source_vertex_ids'],source_clump_labels=z['source_clump_labels'])
budget=.002 if a.method=='local-relax' else .0011
passed=(after['edges_below_2mm']==0 and after['faces_below_15deg']==0
    and after['nonmanifold_edges']==0 and after['boundary_edges']==0 and after['components']==1 and deviation<=budget)
report=dict(method=method,
    source=str(source),source_sha256=hashlib.sha256((source/'geometric_volume.npz').read_bytes()).hexdigest(),
    before=before,after=after,parameters=params,symmetric_vertex_surface_deviation_max_m=deviation,
    quality_gate_pass=passed,proxy_surface_deviation_budget_m=budget,display_mesh_modified=False,physics_started=False,
    versions={k:importlib.metadata.version(k) for k in ['pymeshlab','libigl','numpy']})
(out/'mesh_quality.json').write_text(json.dumps(report,indent=2),'utf8')
asset=json.loads((source/'volume_asset.json').read_text('utf8'));asset.update(vertices=len(newv),triangles=len(newf),
    mesh_quality_regularization=report,manifold_cleanup=True,physics_started=False)
(out/'volume_asset.json').write_text(json.dumps(asset,indent=2),'utf8')
emit('STATIC_QUALITY_PASS' if passed else 'STATIC_QUALITY_REQUIRES_REVIEW',**report)
