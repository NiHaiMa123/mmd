"""Finite-width geometry guard for a mature MMD physics bone bake.

This does not integrate motion or add a head-rest spring. It only enforces the
original display mesh edge bounds and sampled skin separation after skinning.
"""
import sys,json,argparse,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
from mmd_hair_dynamics.contact_islands import ContactIslandProjector
p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--out',required=True);p.add_argument('--frames');p.add_argument('--global-strain',action='store_true');p.add_argument('--safe-reference');p.add_argument('--physics-gain',type=float,default=.25);p.add_argument('--component-fallback',action='store_true');a=p.parse_args();raw=Path(a.raw);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
src=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware';x0=np.load(src/'hair_initial.npy');hard=np.load(src/'hard_roots.npy');body=np.load(src/'body.npy',mmap_mode='r');bones=np.load(src/'anchors.npy',mmap_mode='r');motion=np.load(raw/'positions.npy',mmap_mode='r')
reference=np.load(Path(a.safe_reference)/'positions.npy',mmap_mode='r') if a.safe_reference else None
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
freeids=np.flatnonzero(~hard);lookup=np.full(len(x0),-1);lookup[freeids]=np.arange(len(freeids));edge_all=np.load(src/'hair_edges.npy');fe=edge_all[(~hard[edge_all]).all(1)];fe=lookup[fe];fg=coo_matrix((np.ones(len(fe)*2),(np.r_[fe[:,0],fe[:,1]],np.r_[fe[:,1],fe[:,0]])),shape=(len(freeids),len(freeids))).tocsr();_,flabel=connected_components(fg);labels=np.full(len(x0),-1);labels[freeids]=flabel;disabled=set();disabled_mask=np.zeros(len(x0),dtype=bool);fallbacks=[]
solver=SurfaceProjector(x0,np.load(src/'hair_edges.npy'),np.load(src/'hair_faces.npy'),body[0],np.load(src/'body_faces.npy'),rest=np.load(src/'hair_original.npy'),hard=hard,body_real_faces=np.load(src/'real_body_faces.npy'))
solver.enable_partitioned_body(np.load(src/'body_face_role.npy'),json.loads((src/'body_role_names.json').read_text('utf8')));islands=ContactIslandProjector(solver)
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
ed=solver.host_edges;el=np.linalg.norm(x0[ed[:,0]]-x0[ed[:,1]],axis=1);graph=coo_matrix((np.r_[el,el],(np.r_[ed[:,0],ed[:,1]],np.r_[ed[:,1],ed[:,0]])),shape=(len(x0),len(x0))).tocsr();distance=dijkstra(graph,directed=False,indices=np.flatnonzero(hard),min_only=True);solver.margin_extra.assign((.0025*np.clip((distance-.01)/.04,0,1)).astype('f4'))
if a.global_strain:
 from scipy.sparse import coo_matrix,eye
 from scipy.sparse.linalg import factorized
 edges=solver.host_edges;length=np.linalg.norm(solver.rest[edges[:,0]]-solver.rest[edges[:,1]],axis=1);edges=edges[length>.0005];length=length[length>.0005];ea,eb=edges.T;col=np.arange(len(edges));B=coo_matrix((np.r_[np.ones(len(edges)),-np.ones(len(edges))],(np.r_[ea,eb],np.r_[col,col])),shape=(len(x0),len(edges))).tocsr();L=(B@B.T).tocsc();free=np.flatnonzero(~hard);fixed=np.flatnonzero(hard);strength=10000.;factor=factorized(eye(len(free),format='csc')+strength*L[free][:,free]);Lfh=L[free][:,fixed]
 def global_projection(target):
  x=solver.positions().astype('f8');base=target[free]-strength*(Lfh@target[fixed])
  for _ in range(12):
   d=x[ea]-x[eb];l=np.linalg.norm(d,axis=1);projected=d*(np.clip(l,length*.92,length*1.08)/np.maximum(l,1e-12))[:,None];x[free]=factor(base+strength*(B@projected)[free]);x[fixed]=target[fixed]
  solver.x.assign(x.astype('f4'))
assert not (out/'positions.npy').exists(),'Preserve existing guard output'
positions=np.lib.format.open_memmap(out/'positions.npy',dtype='<f4',mode='w+',shape=motion.shape)
frames=[float(f) for f in a.frames.split(',')] if a.frames else np.arange(1,450.01,.125)
rows=[];started=time.monotonic();previous=None;correction=np.zeros_like(x0)
def status(stage,**extra):
    q=out/'status.tmp.json';q.write_text(json.dumps(dict(stage=stage,**extra),indent=2),'utf8');q.replace(out/'status.json')
try:
 for f in frames:
    k=round((f-1)*8);target=motion[k].copy()
    if reference is not None:
        h=bones[k,-1]@np.linalg.inv(bones[0,-1]);rigid=x0@h[:3,:3].T+h[:3,3];target=reference[k]+a.physics_gain*(target-rigid);target[hard]=rigid[hard]
        if disabled:target[disabled_mask]=reference[k,disabled_mask]
    if previous is not None and k==previous+1:
        rotation=bones[k,-1,:3,:3]@bones[previous,-1,:3,:3].T
        warm=target+.95*(correction@rotation.T)
    else:warm=target.copy()
    warm[hard]=target[hard];solver.x.assign(warm);solver.set_target(target);solver.body_update(body[k]);events=[]
    accepted=False;retry=0
    for retry in range(2):
     if retry:solver.x.assign(target.astype('f4'));events.append(dict(status='DISCARDED_PREVIOUS_GEOMETRIC_WARM_START',physical_bone_state_reset=False))
     for iteration in range(0,2112 if a.component_fallback else 8256,64):
        if a.global_strain:global_projection(solver.positions())
        solver.project(iterations=64,margin=.0005,lo=.905,hi=1.095,triangles=True,max_displacement=.4,material=False)
        if disabled:
            xx=solver.positions();xx[disabled_mask]=reference[k,disabled_mask];solver.x.assign(xx)
        hits,pinned=solver.body_crossings();metrics=solver.metrics()
        if hits==0 and metrics['inside_vertices']==0 and metrics['min_edge_ratio']>=.8995 and metrics['max_edge_ratio']<=1.1005:accepted=True;break
        if pinned:raise RuntimeError(f'Actual fixed-root crossing at {f}')
        if iteration and iteration%1024==0 and (hits or metrics['inside_vertices']):events+=islands.project(.0005)
     if accepted:break
    if not accepted and a.component_fallback and reference is not None:
        xx=solver.positions();ee=solver.host_edges;ll=np.linalg.norm(solver.rest[ee[:,0]]-solver.rest[ee[:,1]],axis=1);valid=ll>.0005;ratio=np.ones(len(ee));ratio[valid]=np.linalg.norm(xx[ee[valid,0]]-xx[ee[valid,1]],axis=1)/ll[valid];bad=ee[(ratio<.8995)|(ratio>1.1005)].ravel();inside,_=solver.distances(xx);bad=np.r_[bad,np.flatnonzero(inside<-.0001),solver.host_faces[solver.crossing_faces()].ravel()];new=set(labels[bad].tolist())-{-1}-disabled
        assert new,('No independent free component can repair failure',f,metrics)
        disabled.update(new);disabled_mask=np.isin(labels,list(disabled));xx[disabled_mask]=reference[k,disabled_mask];xx[hard]=target[hard];solver.x.assign(xx);hits,pinned=solver.body_crossings();metrics=solver.metrics();accepted=hits==metrics['inside_vertices']==0 and metrics['min_edge_ratio']>=.8995 and metrics['max_edge_ratio']<=1.1005
        event=dict(frame=float(f),components=sorted(new),new_reference_vertices=int(np.isin(labels,list(new)).sum()),total_reference_vertices=int(disabled_mask.sum()),policy='same components use validated reference for the entire clip; no per-frame gain switch; no new physical root IDs');fallbacks.append(event);events.append(event);print('AUTOMATIC_COMPONENT_REFERENCE_FALLBACK',json.dumps(event),flush=True)
    if not accepted:raise RuntimeError(f'Guard did not converge at {f}: {metrics}, crossings={hits}')
    x=solver.positions();correction=x-target;correction[hard]=0;previous=k;positions[k]=x;positions.flush()
    row=dict(frame=float(f),sample=k,iterations=iteration+64,retry=retry,crossings=hits,**metrics,max_geometric_correction_m=float(np.linalg.norm(correction,axis=1).max()),rms_geometric_correction_m=float(np.sqrt(np.mean(np.sum(correction**2,axis=1)))),events=events);rows.append(row)
    if len(rows)%8==0 or a.frames:
        status('GEOMETRY_GUARD_RUNNING',**row,elapsed_s=time.monotonic()-started);(out/'guard_rows.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(row),flush=True)
 if disabled:
  for start in range(0,len(positions),32):
   stop=min(start+32,len(positions));block=positions[start:stop].copy();block[:,disabled_mask]=reference[start:stop,disabled_mask];positions[start:stop]=block
  positions.flush()
 report=dict(policy='whole-clip connected free-component reference fallback; physical root mask unchanged',disabled_components=sorted(disabled),disabled_free_vertices=int(disabled_mask.sum()),all_free_vertices=int((~hard).sum()),retained_physical_free_vertices=int(((~hard)&(~disabled_mask)).sum()),events=fallbacks)
 (out/'component_fallback.json').write_text(json.dumps(report,indent=2),'utf8');np.save(out/'component_labels.npy',labels)
 status('GEOMETRY_GUARD_COMPLETE_REQUIRES_NATIVE_AND_VISUAL_QA',samples=len(rows),**report,elapsed_s=time.monotonic()-started);(out/'guard_rows.json').write_text(json.dumps(rows,indent=2),'utf8')
except BaseException as exc:
 status('FAILED',error=repr(exc),last_accepted=rows[-1] if rows else None);raise
