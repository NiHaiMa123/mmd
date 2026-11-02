"""Repair inherited contact-reference popping with a constrained time filter.

Only automatically detected fast free components are processed. Mature Bullet
motion is already baked; this is a finite-width animation postprocess.
"""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
from scipy.signal import butter,sosfiltfilt
from scipy.sparse import coo_matrix,eye
from scipy.sparse.linalg import factorized
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools/contact_stack'))
from mmd_hair_dynamics.gpu_surface import SurfaceProjector
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--run',required=True);p.add_argument('--out',required=True);p.add_argument('--speed-limit',type=float,default=3.);p.add_argument('--cutoff-hz',type=float,default=4.);p.add_argument('--episode-radius-frames',type=float,default=12.);p.add_argument('--avoid-failures');a=p.parse_args();src=Path(a.input);run=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
manifest=json.loads((src/'export_complete.json').read_text('utf8'));original=np.load(run/'positions.npy',mmap_mode='r');head=np.load(src/'anchors.npy',mmap_mode='r')[:,-1];hard=np.load(src/'hard_roots.npy');labels=np.load(run/'component_labels.npy');edges=np.load(src/'hair_edges.npy');faces=np.load(src/'hair_faces.npy');rest=np.load(src/'hair_original.npy');body=np.load(src/'body.npy',mmap_mode='r');dt=manifest['sample_step']/manifest['fps'];previous=None;bad=set();component_speed={};episode_centres={}
for k in range(0,len(original),8):
 inv=np.linalg.inv(head[k]);local=original[k]@inv[:3,:3].T+inv[:3,3]
 if previous is not None:
  speed=np.linalg.norm(local-previous,axis=1)*30;bad.update(labels[(speed>a.speed_limit)&(~hard)].tolist())
  for c in np.unique(labels[(speed>a.speed_limit)&(~hard)]):component_speed[int(c)]=max(component_speed.get(int(c),0),float(speed[labels==c].max()));episode_centres.setdefault(int(c),[]).append(k)
 previous=local
bad.discard(-1);mobile=np.isin(labels,list(bad));selected_faces=np.any(mobile[faces],axis=1);selected_edges=np.any(mobile[edges],axis=1);ids=np.unique(np.r_[faces[selected_faces].ravel(),edges[selected_edges].ravel()]);lookup=np.full(len(hard),-1);lookup[ids]=np.arange(len(ids));hf=lookup[faces[selected_faces]];ee=lookup[edges[selected_edges]];h=hard[ids];assert np.all(h|mobile[ids]);fixed=np.flatnonzero(h);free=np.flatnonzero(~h)
assert len(ids)>0 and not (out/'positions.npy').exists();print('TEMPORAL_COMPONENTS',json.dumps(dict(components=sorted(bad),vertices=len(ids),free_vertices=len(free),old_speed=component_speed)),flush=True)
local=np.lib.format.open_memmap(out/'filtered_head_local.npy',dtype='<f4',mode='w+',shape=(len(original),len(ids),3))
for k in range(len(original)):
 inv=np.linalg.inv(head[k]);local[k]=original[k,ids]@inv[:3,:3].T+inv[:3,3]
sos=butter(4,a.cutoff_hz,fs=1/dt,output='sos')
envelope={};timeline=np.arange(len(original));radius=a.episode_radius_frames*8
for c,centres in episode_centres.items():
 weight=np.zeros(len(original))
 for centre in centres:
  phase=(timeline-centre)/radius;weight=np.maximum(weight,np.where(abs(phase)<1,.5+.5*np.cos(np.pi*np.clip(phase,-1,1)),0))
 envelope[c]=weight
avoid=json.loads(Path(a.avoid_failures).read_text('utf8')) if a.avoid_failures else []
for event in avoid:
 phase=(timeline-event['sample'])/(event.get('radius_frames',2)*8);notch=np.where(abs(phase)<1,.5-.5*np.cos(np.pi*np.clip(phase,-1,1)),1)
 for c in event['components']:
  if c in envelope:envelope[c]*=notch
for start in range(0,len(ids),256):
 stop=min(start+256,len(ids));before=np.asarray(local[:,start:stop],dtype='f8');filtered=sosfiltfilt(sos,before,axis=0);weights=np.column_stack([envelope.get(int(c),np.zeros(len(original))) for c in labels[ids[start:stop]]]);local[:,start:stop]=(before+(filtered-before)*weights[:,:,None]).astype('f4')
local.flush()
solver=SurfaceProjector(original[0,ids],ee,hf,body[0],np.load(src/'body_faces.npy'),rest=rest[ids],hard=h,body_real_faces=np.load(src/'real_body_faces.npy'))
solver.enable_partitioned_body(np.load(src/'body_face_role.npy'),json.loads((src/'body_role_names.json').read_text('utf8')))
length=np.linalg.norm(rest[ids][ee[:,0]]-rest[ids][ee[:,1]],axis=1);active=ee[length>.0005];length=length[length>.0005];ea,eb=active.T;col=np.arange(len(active));B=coo_matrix((np.r_[np.ones(len(active)),-np.ones(len(active))],(np.r_[ea,eb],np.r_[col,col])),shape=(len(ids),len(active))).tocsr();L=(B@B.T).tocsc();strength=10000.;factor=factorized(eye(len(free),format='csc')+strength*L[free][:,free]);Lfh=L[free][:,fixed]
def global_projection(target):
 x=solver.positions().astype('f8');base=target[free]-strength*(Lfh@target[fixed])
 for _ in range(12):
  d=x[ea]-x[eb];l=np.linalg.norm(d,axis=1);proj=d*(np.clip(l,length*.92,length*1.08)/np.maximum(l,1e-12))[:,None];x[free]=factor(base+strength*(B@proj)[free]);x[fixed]=target[fixed]
 solver.x.assign(x.astype('f4'))
positions=np.lib.format.open_memmap(out/'positions.npy',dtype='<f4',mode='w+',shape=original.shape);rows=[];fallback=set();fallback_events=[];previous_correction=np.zeros((len(ids),3));started=time.monotonic()
def status(stage,**kw):
 q=out/'status.tmp.json';q.write_text(json.dumps(dict(stage=stage,**kw),indent=2),'utf8');q.replace(out/'status.json')
try:
 for k in range(len(original)):
  target=local[k]@head[k,:3,:3].T+head[k,:3,3];target[h]=original[k,ids[h]]
  if k<32:
   mix=.5-.5*np.cos(np.pi*k/32);target=original[k,ids]*(1-mix)+target*mix
  blocked=np.isin(labels[ids],list(fallback));target[blocked]=original[k,ids[blocked]]
  correction=previous_correction if not k else previous_correction@(head[k,:3,:3]@head[k-1,:3,:3].T).T
  solver.x.assign((target+.8*correction).astype('f4'));solver.set_target(target);solver.body_update(body[k]);accepted=False
  for retry in range(2):
   if retry:solver.x.assign(target.astype('f4'))
   hits,pinned=solver.body_crossings();m=solver.metrics();it=-64
   if hits==m['inside_vertices']==0 and m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005:accepted=True;break
   for it in range(0,2112,64):
    global_projection(solver.positions());solver.project(iterations=64,margin=.0005,lo=.905,hi=1.095,triangles=True,max_displacement=.25,material=False)
    if fallback:
     xx=solver.positions();xx[blocked]=original[k,ids[blocked]];solver.x.assign(xx)
    hits,pinned=solver.body_crossings();m=solver.metrics()
    if hits==m['inside_vertices']==0 and m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005:accepted=True;break
    assert pinned==0,('Fixed-root conflict',k)
   if accepted:break
  if not accepted:
   xx=solver.positions();len0=np.linalg.norm(rest[ids][ee[:,0]]-rest[ids][ee[:,1]],axis=1);valid=len0>.0005;r=np.ones(len(ee));r[valid]=np.linalg.norm(xx[ee[valid,0]]-xx[ee[valid,1]],axis=1)/len0[valid];badvertices=ee[(r<.8995)|(r>1.1005)].ravel();dd,_=solver.distances(xx);badvertices=np.r_[badvertices,np.flatnonzero(dd<-.0001),hf[solver.crossing_faces()].ravel()];new=set(labels[ids[badvertices]].tolist())-{-1}-fallback;assert new,('No new fallback component',k,m);fallback.update(new);fallback_events.append(dict(sample=k,components=sorted(new),radius_frames=2));blocked=np.isin(labels[ids],list(fallback));xx[blocked]=original[k,ids[blocked]];xx[h]=target[h];solver.x.assign(xx);hits,pinned=solver.body_crossings();m=solver.metrics();assert hits==m['inside_vertices']==0 and m['min_edge_ratio']>=.8995 and m['max_edge_ratio']<=1.1005,('Temporal projection failure',k,m);print('TEMPORAL_FALLBACK',k,sorted(new),flush=True)
  xx=solver.positions();previous_correction=xx-target;whole=original[k].copy();whole[ids]=xx;positions[k]=whole
  rows.append(dict(frame=1+k/8,sample=k,iterations=it+64,crossings=hits,**m))
  if k%80==0:positions.flush();status('TEMPORAL_CONTACT_GUARD_RUNNING',sample=k,frame=1+k/8,filtered_components=sorted(bad),fallback_components=sorted(fallback),elapsed_s=time.monotonic()-started);print(json.dumps(rows[-1]),flush=True)
 if fallback:
  mask=np.isin(labels,list(fallback))
  for k in range(0,len(original),32):
   block=positions[k:k+32].copy();block[:,mask]=original[k:k+32,mask];positions[k:k+32]=block
 positions.flush();(out/'guard_rows.json').write_text(json.dumps(rows,indent=2),'utf8');base=json.loads((run/'component_fallback.json').read_text('utf8'));(out/'component_fallback.json').write_text(json.dumps(base,indent=2),'utf8');np.save(out/'component_labels.npy',labels);(out/'temporal_filter.json').write_text(json.dumps(dict(method='fourth order zero-phase Butterworth in head coordinates, cosine envelope around automatically detected popping episodes, renewed contact and edge projection, automatic smooth notches at prior infeasible projection episodes',speed_detection_m_s=a.speed_limit,cutoff_hz=a.cutoff_hz,episode_radius_frames=a.episode_radius_frames,episode_centres=episode_centres,avoid_projection_episodes=avoid,fallback_events=fallback_events,filtered_components=sorted(bad),filtered_free_vertices=int(mobile.sum()),unresolved_temporal_components=sorted(fallback),source=str(run),source_component_speeds=component_speed),indent=2),'utf8');status('GEOMETRY_GUARD_COMPLETE_REQUIRES_NATIVE_AND_VISUAL_QA',samples=len(rows),filtered_components=sorted(bad),unresolved_temporal_components=sorted(fallback),elapsed_s=time.monotonic()-started)
except BaseException as exc:status('FAILED',error=repr(exc),last_sample=rows[-1] if rows else None);raise
