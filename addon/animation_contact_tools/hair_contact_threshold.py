"""Measure the extent of each connected embedded display-hair patch.

Contact measurement only. Does not alter geometry, animation, or physics.
"""
import numpy as np


def embedded_patch_metrics(points, signed_distance, edges, limit_m=.05, inside_epsilon_m=.0001,
                           limit_mode='extent_or_depth'):
    if limit_mode not in {'extent_or_depth', 'depth'}:
        raise ValueError('Unknown hair contact limit mode: '+str(limit_mode))
    points=np.asarray(points,dtype=float);distance=np.asarray(signed_distance)
    inside=distance < -inside_epsilon_m;indices=np.flatnonzero(inside)
    parent=np.arange(len(points),dtype=np.int32)
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
        return i
    relevant=np.asarray(edges)[inside[np.asarray(edges)[:,0]] & inside[np.asarray(edges)[:,1]]]
    for aa,bb in relevant:
        a=find(int(aa));b=find(int(bb))
        if a!=b:parent[b]=a
    components={}
    for i in indices:components.setdefault(find(int(i)),[]).append(int(i))
    patches=[]
    for members in components.values():
        q=points[members];diagonal=float(np.linalg.norm(np.ptp(q,axis=0)))
        # Exact Euclidean diameter; block queries bound temporary memory.
        diameter2=0.
        for start in range(0,len(q),256):
            delta=q[start:start+256,None,:]-q[None,:,:]
            diameter2=max(diameter2,float(np.einsum('ijk,ijk->ij',delta,delta).max()))
        diameter=float(np.sqrt(diameter2));depth=float(max(0,-distance[members].min()))
        patches.append(dict(vertices=len(members),local_vertex_ids=members,maximum_spatial_extent_m=diameter,
                            bounding_box_diagonal_m=diagonal,maximum_depth_m=depth,
                            exceeds_depth_limit=bool(depth>limit_m),
                            exceeds_extent_limit=bool(diameter>limit_m),
                            exceeds_limit=bool(depth>limit_m or
                                               (limit_mode=='extent_or_depth' and diameter>limit_m))))
    patches.sort(key=(lambda p:p['maximum_depth_m']) if limit_mode=='depth' else
                 (lambda p:max(p['maximum_spatial_extent_m'],p['maximum_depth_m'])),reverse=True)
    return dict(limit_m=float(limit_m),limit_mode=limit_mode,
                inside_vertices=len(indices),connected_inside_patches=len(patches),
                maximum_depth_m=float(max(0,-distance.min())),
                maximum_patch_extent_m=max((p['maximum_spatial_extent_m'] for p in patches),default=0.),
                exceeds_limit=any(p['exceeds_limit'] for p in patches),patches=patches)
