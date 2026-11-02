"""Discrete contact-seed paths for an explicitly declared two-hand interval.

Uses actual source hand triangles and keeps finger poses/hand rotations.
This is an initialization proposal. Rig skinning and subframes need separate
validation; no cloth solve, semantic detection or continuous guarantee here.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .motion_contact import triangle_crosses


def remap_faces(ids,faces):
    mapping={int(v):i for i,v in enumerate(ids)}
    return np.array([[mapping[int(v)] for v in f] for f in faces],dtype=np.int32)


def crosses(left,right,faces_left,faces_right,left_tree=None):
    tl=left_tree or BVHTree.FromPolygons(left.tolist(),faces_left.tolist(),all_triangles=True)
    tr=BVHTree.FromPolygons(right.tolist(),faces_right.tolist(),all_triangles=True)
    for i,j in tl.overlap(tr):
        if triangle_crosses([Vector(v) for v in left[faces_left[i]]],[Vector(v) for v in right[faces_right[j]]]):return True
    return False


def contact_seed_path(vertices,ids_left,ids_right,faces_left,faces_right,left_rotations,*,rays=96,max_translation=.08,max_local_step=.018,edge_checks=3,required_local_direction=(0.,0.,-1.),source_wrist_separation=None,cached_layers=None,progress=None):
    """Layered graph search; return failure rather than an unconnected track.

    Positions are world coordinates; costs compare translations in each left
    wrist frame. Edge checks interpolate source meshes only for proposal
    filtering. The actual animated rig must be checked independently.
    """
    fl=remap_faces(ids_left,faces_left);fr=remap_faces(ids_right,faces_right)
    ls=vertices[:,ids_left];rs=vertices[:,ids_right];layers=[]
    required=None if required_local_direction is None else np.asarray(required_local_direction,dtype=float)
    if required is not None:
        if required.shape!=(3,) or np.linalg.norm(required)<1e-8:raise ValueError('Declare a nonzero contact-side direction')
        required=required/np.linalg.norm(required)
        if source_wrist_separation is None:raise ValueError('Contact-side preservation needs the actual source wrist separation; correction sign is not hand order')
        source_wrist_separation=np.asarray(source_wrist_separation,dtype=float)
        if source_wrist_separation.shape!=(len(vertices),3) or not np.isfinite(source_wrist_separation).all():raise ValueError('Source wrist separation must be a finite T by 3 array')
    for frame,(left,right,rotation) in enumerate(zip(ls,rs,left_rotations)):
        tl=BVHTree.FromPolygons(left.tolist(),fl.tolist(),all_triangles=True);candidates=[]
        if cached_layers is not None and frame in cached_layers:
            for value in cached_layers[frame]:
                value=np.asarray(value,dtype=float)
                if value.shape!=(3,) or not np.isfinite(value).all() or np.linalg.norm(value)>max_translation:continue
                if required is not None and source_wrist_separation is not None and np.dot(rotation.T@(source_wrist_separation[frame]+value),required)<.003:continue
                if crosses(left,right-value,fl,fr,tl):continue
                candidates.append(value)
            if not candidates:raise ValueError(f'No valid cached candidate at sample {frame}')
            layers.append(np.array(candidates))
            if progress:progress('candidate_layer',frame,{'vectors':np.array(candidates).tolist()});progress('candidates',frame,{'count':len(candidates),'revalidated_cache':True})
            continue
        directions=[]
        for i in range(rays):
            z=1-2*(i+.5)/rays;theta=np.pi*(3-np.sqrt(5))*i;directions.append(rotation@np.array([np.sqrt(1-z*z)*np.cos(theta),np.sqrt(1-z*z)*np.sin(theta),z]))
        directions.extend([rotation@v for v in (np.array([0.,0.,-1.]),np.array([0.,0.,1.]))])
        # Preserve the FINAL wrist-side relation, not the sign of a correction.
        # The latter unnecessarily forbids contact sliding toward the source.
        for direction in directions:
            bound=max_translation
            if required is not None and source_wrist_separation is not None:
                initial_side=float(np.dot(rotation.T@source_wrist_separation[frame],required));speed=float(np.dot(rotation.T@direction,required))
                if initial_side<.003:raise ValueError('The declared source wrist side is ambiguous or changes phase')
                if speed<0:bound=min(bound,(initial_side-.003)/(-speed))
            last=0.;first=None
            for distance in np.arange(.004,bound+.00001,.004):
                if not crosses(left,right-direction*distance,fl,fr,tl):first=distance;break
                last=distance
            if first is None:continue
            lo,hi=last,first
            for _ in range(7):
                middle=(lo+hi)*.5
                if crosses(left,right-direction*middle,fl,fr,tl):lo=middle
                else:hi=middle
            delta=direction*(hi+.002)
            if np.linalg.norm(delta)>max_translation or crosses(left,right-delta,fl,fr,tl):continue
            if required is not None and source_wrist_separation is not None and np.dot(rotation.T@(source_wrist_separation[frame]+delta),required)<.003:continue
            if any(np.linalg.norm(delta-v)<.001 for v in candidates):continue
            candidates.append(delta)
        if not candidates:raise ValueError(f'No bounded contact candidates at sample {frame}')
        layers.append(np.array(candidates))
        if progress:progress('candidate_layer',frame,{'vectors':np.array(candidates).tolist()})
        if progress:progress('candidates',frame,{'count':len(candidates)})
    cost=np.sum(layers[0]**2,axis=1);parents=[];edge_rejections=0
    for frame in range(1,len(layers)):
        previous=layers[frame-1];current=layers[frame];old_local=previous@left_rotations[frame-1];new_local=current@left_rotations[frame];dist=np.linalg.norm(new_local[:,None]-old_local[None],axis=-1);current_cost=np.full(len(current),np.inf);parent=np.full(len(current),-1,dtype=int)
        for j,node in enumerate(current):
            estimate=cost+8*dist[j]**2+.02*np.dot(node,node)
            for i in np.argsort(estimate):
                if not np.isfinite(estimate[i]):break
                if dist[j,i]>max_local_step:continue
                clear=True
                for t in np.linspace(0,1,edge_checks+2)[1:-1]:
                    left=(1-t)*ls[frame-1]+t*ls[frame];right=(1-t)*rs[frame-1]+t*rs[frame];delta=(1-t)*previous[i]+t*node
                    if required is not None and source_wrist_separation is not None:
                        normal=(1-t)*(left_rotations[frame-1]@required)+t*(left_rotations[frame]@required);normal/=np.linalg.norm(normal);separation=(1-t)*source_wrist_separation[frame-1]+t*source_wrist_separation[frame]
                        if np.dot(separation+delta,normal)<.003:clear=False;edge_rejections+=1;break
                    if crosses(left+delta*.5,right-delta*.5,fl,fr):clear=False;edge_rejections+=1;break
                if clear:current_cost[j]=estimate[i];parent[j]=i;break
        if np.all(parent<0):raise ValueError(f'No collision-free graph edge reaches sample {frame}')
        cost=current_cost;parents.append(parent)
        if progress:progress('edges',frame,{'reachable':int(np.isfinite(cost).sum()),'rejected_edges':edge_rejections})
    index=int(np.argmin(cost));path=[layers[-1][index]]
    for frame in range(len(layers)-1,0,-1):index=int(parents[frame-1][index]);path.append(layers[frame-1][index])
    path=np.array(path[::-1]);local=np.einsum('tji,tj->ti',left_rotations,path)
    return path,{'candidate_counts':[len(v) for v in layers],'edge_rejections':edge_rejections,'interior_checks_per_edge':edge_checks,'required_local_direction':None if required is None else required.tolist(),'max_local_translation_step_m':float(np.linalg.norm(np.diff(local,axis=0),axis=1).max()),'max_per_hand_translation_m':float(np.linalg.norm(path,axis=1).max()*.5),'scope':'Discrete translation graph with interpolated input mesh edge proposals; declared contact-side constraint, actual rig/subframe/gesture validation required'}
