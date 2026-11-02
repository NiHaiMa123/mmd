"""Conservatively represent ill-conditioned prescribed collider faces by boxes.

No original skin triangle is dropped from collision coverage: each replaced
triangle lies inside its 0.2mm-padded animated oriented box. This is only an
auxiliary collider representation; the original model and animation stay put.
"""
import argparse,json,shutil
from pathlib import Path
import numpy as np

def transported_axes(u,first_v):
    """Keep a thin face's box frame continuous when its plane normal folds."""
    u=u.copy();dots=np.einsum('fi,fi->f',u[1:],u[:-1]);sign=np.r_[1.,np.cumprod(np.where(dots<0,-1.,1.))];u*=sign[:,None]
    result=[];previous=first_v
    for direction in u:
        v=previous-np.dot(previous,direction)*direction;length=np.linalg.norm(v)
        if length<.1:raise ValueError('Thin-face long axis changes too far for transport; adapt its collision representation')
        v/=length;n=np.cross(direction,v);result.append(np.stack((direction,v,n),axis=1));previous=v
    return np.asarray(result)

p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);p.add_argument('--padding',type=float,default=.0002);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a fresh conditioned collider directory')
if (src/'volume_binding.npz').exists():shutil.copyfile(src/'volume_binding.npz',out/'volume_binding.npz')
with np.load(src/'trajectories.npz') as archive:d={k:archive[k] for k in archive.files}
body=d['body'];faces=d['body_faces'];tri=body[0][faces];sv=np.linalg.svd(np.stack((tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=2),compute_uv=False);bad=np.flatnonzero(sv[:,1]/np.maximum(sv[:,0],1e-15)<.001)
if not 0<a.padding<=.0005:raise ValueError('Collider padding must be explicit and at most 0.5mm')
box_faces=np.array([(0,2,3),(0,3,1),(4,5,7),(4,7,6),(0,1,5),(0,5,4),(2,6,7),(2,7,3),(0,4,6),(0,6,2),(1,3,7),(1,7,5)])
box_faces=box_faces[:,::-1]  # outward winding in the binary corner order
signs=np.array([(x,y,z) for x in (0,1) for y in (0,1) for z in (0,1)])
bad_set=set(bad.tolist());extra=[];new_faces=[f for k,f in enumerate(faces) if k not in bad_set];worst=-float('inf');minimum_axis_dot=1.;transported=[];interpolated_worst=-float('inf')
for k,face_index in enumerate(bad):
    points=body[:,faces[face_index]];centers=points.mean(1);pairs=[(0,1),(1,2),(2,0)];aa,bb=max(pairs,key=lambda ab:float(np.linalg.norm(points[0,ab[0]]-points[0,ab[1]])))
    u=points[:,bb]-points[:,aa];edge_length=np.linalg.norm(u,axis=1)
    if edge_length.min()<1e-10:raise ValueError('Collapsed thin-face long edge needs a different explicit collider')
    u/=edge_length[:,None];normal=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-20);v=np.cross(normal,u);axes=np.stack((u,v,normal),axis=2)
    if len(axes)>1 and np.min(np.sum(axes[1:]*axes[:-1],axis=1))<.8:
        if np.linalg.norm(v[0])<.9:raise ValueError('Invalid initial thin-face frame')
        axes=transported_axes(u,v[0]);transported.append(int(face_index))
    if len(axes)>1:minimum_axis_dot=min(minimum_axis_dot,float(np.min(np.sum(axes[1:]*axes[:-1],axis=1))))
    local=np.einsum('fvi,fij->fvj',points-centers[:,None,:],axes);low=local.min(1)-a.padding;high=local.max(1)+a.padding;box_local=low[:,None,:]*(1-signs[None,:,:])+high[:,None,:]*signs[None,:,:];boxes=np.einsum('fvj,fij->fvi',box_local,axes)+centers[:,None,:];worst=max(worst,float(np.max(np.maximum(low[:,None,:]-local,local-high[:,None,:]))));extra.append(boxes)
    for fraction in (.25,.5,.75):
        if len(boxes)<2:break
        b=boxes[:-1]*(1-fraction)+boxes[1:]*fraction;p=points[:-1]*(1-fraction)+points[1:]*fraction;basis=np.stack((b[:,4]-b[:,0],b[:,2]-b[:,0],b[:,1]-b[:,0]),axis=2);inverse=np.linalg.inv(basis);coefficients=np.einsum('fij,fvj->fvi',inverse,p-b[:,None,0]);height=1/np.linalg.norm(inverse,axis=2);violation=np.maximum(-coefficients,coefficients-1)*height[:,None,:];interpolated_worst=max(interpolated_worst,float(violation.max()))
    if interpolated_worst>1e-8:raise ValueError('Interpolated collider box misses original skin; resample or enlarge its explicit padding')
    offset=body.shape[1]+8*k;new_faces.extend((box_faces+offset).tolist())
if minimum_axis_dot<.8:raise ValueError('Degenerate face frame rotates too far; resample or adapt before using animated boxes')
if extra:d['body']=np.concatenate((body,*extra),axis=1)
d['body_faces']=np.asarray(new_faces,dtype=int)
tri=d['body'][0][d['body_faces']];sv=np.linalg.svd(np.stack((tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=2),compute_uv=False);minimum=float(np.min(sv[:,1]/np.maximum(sv[:,0],1e-15)))
if minimum<.0003453:raise ValueError('Conditioned collider still exceeds the native rest-shape condition bound')
np.savez_compressed(out/'trajectories.npz',**d);manifest=json.loads((src/'manifest.json').read_text('utf8'));receipt=dict(source=str(src),replaced_faces=len(bad),original_triangle_indices=bad.tolist(),padding_m=a.padding,coverage_max_halfspace_violation_m=worst,minimum_frame_axis_dot=minimum_axis_dot,minimum_rest_shape_condition=minimum,source_model_modified=False,all_original_faces_represented=True,body_animation_modified=False)
receipt.update(transported_frame_faces=transported,coverage_interpolated_max_halfspace_violation_m=interpolated_worst if np.isfinite(interpolated_worst) else None,coverage_interpolation_fractions=[.25,.5,.75],continuous_source_coverage_proven=False)
manifest['collider_conditioning']=receipt;(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');(out/'collider_conditioning.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print('CONSERVATIVE_COLLIDER',json.dumps({k:v for k,v in receipt.items() if k!='original_triangle_indices'}),flush=True)
