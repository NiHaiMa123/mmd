"""Bounded PBD corrective for an already simulated finite-width hair surface.

Quasi-static contact/edge-strain projection, not a replacement dynamics or CCD
solver. Original bodies never enter the DOFs. Final triangle auditing is needed.
"""
import numpy as np


def edge_colours(edges):
    groups=[];used=[]
    for k,(a,b) in enumerate(np.asarray(edges,dtype=int)):
        for indices,vertices in zip(groups,used):
            if a not in vertices and b not in vertices:indices.append(k);vertices.update((int(a),int(b)));break
        else:groups.append([k]);used.append({int(a),int(b)})
    return [np.asarray(g,dtype=int) for g in groups]


def contact_samples(vertex_count,edges,triangles):
    vertices=np.arange(vertex_count,dtype=int)
    indices=np.vstack((np.column_stack((vertices,vertices,vertices)),np.column_stack((edges[:,0],edges[:,1],edges[:,1])),triangles))
    bary=np.vstack((np.tile([1.,0,0],(vertex_count,1)),np.tile([.5,.5,0],(len(edges),1)),np.full((len(triangles),3),1/3)))
    return indices,bary


def project_surface(target,rest,edges,triangles,pinned,signed_distance,initial=None,
                    margin=.006,strain_limit=.05,max_displacement=.06,iterations=160,
                    target_strength=.008,colours=None,samples=None,previous_positions=None,temporal_projection=.9):
    target=np.asarray(target,dtype=float);x=target.copy() if initial is None else np.asarray(initial,dtype=float).copy();rest=np.asarray(rest,dtype=float);edges=np.asarray(edges,dtype=int);pinned=np.asarray(pinned,dtype=bool)
    if target.shape!=rest.shape or target.ndim!=2 or target.shape[1]!=3:raise ValueError('Matching N x 3 rest and target positions required')
    if not 0<=strain_limit<1 or margin<0 or max_displacement<=0:raise ValueError('Invalid geometry limits')
    mass=(~pinned).astype(float);length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);valid=length>.0005;colours=colours or edge_colours(edges);indices,bary=contact_samples(len(x),edges,np.asarray(triangles,dtype=int)) if samples is None else samples
    previous_direction=None
    if previous_positions is not None:
        previous=np.asarray(previous_positions,dtype=float)
        if previous.shape!=target.shape or not 0<=temporal_projection<=1:raise ValueError('Invalid previous positions or temporal bound')
        previous_direction=previous[edges[:,0]]-previous[edges[:,1]];previous_direction/=np.maximum(np.linalg.norm(previous_direction,axis=1)[:,None],1e-12)
    # A bounded correction cannot reach bodies further away than this band.
    basepoints=np.einsum('si,sij->sj',bary,target[indices]);distance,_=signed_distance(basepoints);active=(distance<margin+max_displacement+.003)&(np.sum(mass[indices]*bary*bary,axis=1)>1e-12);ci,cb=indices[active],bary[active]
    def contacts():
        points=np.einsum('si,sij->sj',cb,x[ci]);distance,normal=signed_distance(points);penetration=np.maximum(margin-distance,0.);weights=mass[ci]*cb;denom=np.sum(weights*cb,axis=1);delta=normal*(penetration/np.maximum(denom,1e-12))[:,None];acc=np.zeros_like(x);count=np.zeros(len(x))
        hit=penetration>1e-8
        for slot in range(3):
            participating=hit&(weights[:,slot]>0);np.add.at(acc,ci[participating,slot],delta[participating]*weights[participating,slot,None]);np.add.at(count,ci[participating,slot],1.)
        x[:]+=acc/np.maximum(count[:,None],1.)
        return float(penetration.max(initial=0.))
    for iteration in range(iterations):
        x[:]+=target_strength*(target-x)*mass[:,None]
        for colour in colours:
            selected=colour[valid[colour]];a,b=edges[selected].T;v=x[a]-x[b];current=np.linalg.norm(v,axis=1);bound=np.clip(current,length[selected]*(1-strain_limit),length[selected]*(1+strain_limit));denom=mass[a]+mass[b];delta=v*((bound-current)/np.maximum(current,1e-12)/np.maximum(denom,1e-12))[:,None];x[a]+=mass[a,None]*delta;x[b]-=mass[b,None]*delta
            if previous_direction is not None:
                direction=previous_direction[selected];projection=np.sum((x[a]-x[b])*direction,axis=1);amount=np.maximum(temporal_projection*length[selected]-projection,0.)/np.maximum(denom,1e-12);delta=direction*amount[:,None];x[a]+=mass[a,None]*delta;x[b]-=mass[b,None]*delta
        if iteration%2==0 or iteration==iterations-1:contacts()
        shift=x-target;distance=np.linalg.norm(shift,axis=1);x[:]=target+shift*np.minimum(1.,max_displacement/np.maximum(distance,1e-12))[:,None];x[pinned]=target[pinned]
    ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)[valid]/length[valid];final_distance,_=signed_distance(np.einsum('si,sij->sj',bary,x[indices]));offset=np.linalg.norm(x-target,axis=1)
    detail={'min_edge_ratio':float(ratio.min()),'max_edge_ratio':float(ratio.max()),'min_sample_distance_m':float(final_distance.min()),'max_correction_m':float(offset.max()),'pinned_error_m':float(np.max(np.abs(x[pinned]-target[pinned]),initial=0.)),'contact_samples':len(indices),'active_contact_samples':len(ci),'iterations':iterations,'continuous_collision_proven':False,'triangle_audit_required':True}
    if previous_direction is not None:detail['min_temporal_edge_projection_ratio']=float((np.sum((x[edges[:,0]]-x[edges[:,1]])*previous_direction,axis=1)[valid]/length[valid]).min())
    return x,detail
