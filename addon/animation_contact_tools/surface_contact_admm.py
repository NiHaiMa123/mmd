"""Experimental global contact/edge projection, NOT a complete dynamics solver.

ADMM splitting propagates a contact correction through the whole edge network.
Only a small clump is supported by this dense NumPy reference implementation.
Final triangle, self-contact, time continuity and source-preservation audits are
separate requirements. A converged linear solve does not establish feasibility.
"""
import numpy as np
from .surface_contact_projection import contact_samples


def project_surface_global(target, rest, edges, triangles, pinned, signed_distance,
                           initial=None, margin=.002, strain_limit=.04,
                           iterations=300, contact_weight=1., edge_weight=5.,
                           target_weight=.001):
    target=np.asarray(target,dtype=float);rest=np.asarray(rest,dtype=float)
    edges=np.asarray(edges,dtype=int);pinned=np.asarray(pinned,dtype=bool)
    if target.shape!=rest.shape or target.ndim!=2 or target.shape[1]!=3 or len(target)>2000:
        raise ValueError('This dense reference requires a matching clump of at most 2000 vertices')
    if not 0<=strain_limit<1 or margin<0 or min(contact_weight,edge_weight,target_weight)<=0:
        raise ValueError('Positive solve weights and valid geometric bounds required')
    x=target.copy() if initial is None else np.asarray(initial,dtype=float).copy()
    original_edges=edges.copy();length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    edges=edges[length>.0005];length=length[length>.0005]
    ci,cb=contact_samples(len(x),original_edges,np.asarray(triangles,dtype=int))
    # All sample rows remain in the global matrix; inactive contact projections
    # are identities. This avoids silently dropping newly active contacts.
    n=len(x);A=np.eye(n)*target_weight;a,b=edges.T
    np.add.at(A,(a,a),edge_weight);np.add.at(A,(b,b),edge_weight)
    np.add.at(A,(a,b),-edge_weight);np.add.at(A,(b,a),-edge_weight)
    for i in range(3):
        for j in range(3):np.add.at(A,(ci[:,i],ci[:,j]),contact_weight*cb[:,i]*cb[:,j])
    free=~pinned;fixed=target[pinned]
    inverse=np.linalg.inv(A[np.ix_(free,free)]);fixed_rhs=A[np.ix_(free,pinned)]@fixed
    ue=np.zeros((len(edges),3));uc=np.zeros((len(ci),3));history=[]
    def scatter_contact(value):
        result=np.zeros_like(x)
        for j in range(3):np.add.at(result,ci[:,j],value*cb[:,j,None])
        return result
    for k in range(iterations):
        delta=x[a]-x[b];edge_trial=delta+ue;norm=np.linalg.norm(edge_trial,axis=1)
        ze=edge_trial*(np.clip(norm,length*(1-strain_limit),length*(1+strain_limit))/np.maximum(norm,1e-12))[:,None]
        points=np.einsum('si,sij->sj',cb,x[ci]);trial=points+uc
        distance,normal=signed_distance(trial)
        zc=trial+normal*np.maximum(margin-distance,0)[:,None]
        rhs=target_weight*target+contact_weight*scatter_contact(zc-uc)
        np.add.at(rhs,a,edge_weight*(ze-ue));np.add.at(rhs,b,-edge_weight*(ze-ue))
        x[free]=inverse@(rhs[free]-fixed_rhs);x[pinned]=fixed
        ue+=x[a]-x[b]-ze;uc+=np.einsum('si,sij->sj',cb,x[ci])-zc
        if not np.all(np.isfinite(x)) or np.max(np.linalg.norm(x-target,axis=1))>.2:
            raise RuntimeError('Global contact reference diverged; candidate rejected')
        if k%50==0:
            ratio=np.linalg.norm(x[a]-x[b],axis=1)/length
            history.append(dict(iteration=k,min_edge_ratio=float(ratio.min()),max_edge_ratio=float(ratio.max())))
    ratio=np.linalg.norm(x[a]-x[b],axis=1)/length
    distance,_=signed_distance(np.einsum('si,sij->sj',cb,x[ci]))
    return x,dict(method='global ADMM contact/edge reference',iterations=iterations,
                  min_edge_ratio=float(ratio.min()),max_edge_ratio=float(ratio.max()),
                  min_sample_distance_m=float(distance.min()),
                  max_correction_m=float(np.linalg.norm(x-target,axis=1).max()),
                  pinned_error_m=float(np.max(np.abs(x[pinned]-target[pinned]),initial=0.)),
                  history=history,continuous_collision_proven=False,triangle_audit_required=True)
