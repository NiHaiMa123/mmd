"""Static garment contact fitting on actual triangles; source geometry preserved.

Not a dynamics solver. Keeps an explicit collision report and bounds movement;
no body deletion, triangle removal, or hidden collision-pair exemptions.
"""
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from .motion_contact import triangle_crosses,inside_votes


def fit_surface(points,faces,skin,skin_faces,*,locked=None,margin=.0015,iterations=60,max_displacement=.08,progress=None):
    points=np.asarray(points,dtype=float);faces=np.asarray(faces,dtype=np.int32);skin=np.asarray(skin,dtype=float);skin_faces=np.asarray(skin_faces,dtype=np.int32)
    # Weld only coincident seam points in the computational graph.
    _,inverse=np.unique(np.rint(points/1e-6).astype(np.int64),axis=0,return_inverse=True);n=int(inverse.max())+1;rest=np.zeros((n,3));counts=np.bincount(inverse);np.add.at(rest,inverse,points);rest/=counts[:,None];tri=inverse[faces];tri=tri[np.array([len(set(f))==3 for f in tri])];x=rest.copy();fixed=np.zeros(n,dtype=bool)
    if locked is not None:np.logical_or.at(fixed,inverse,np.asarray(locked,dtype=bool))
    parent=np.arange(n)
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for f in tri:
        for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
    component=np.array([root(i) for i in range(n)]);groups={c:np.flatnonzero(component==c) for c in np.unique(component)};sticky=np.zeros(n,dtype=bool);tree=BVHTree.FromPolygons(skin.tolist(),skin_faces.tolist(),all_triangles=True);history=[]
    normals=np.cross(skin[skin_faces[:,1]]-skin[skin_faces[:,0]],skin[skin_faces[:,2]]-skin[skin_faces[:,0]]);normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-14)
    edges=np.unique(np.sort(np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])),axis=1),axis=0);rest_lengths=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
    def crossings():
        garment=BVHTree.FromPolygons(x.tolist(),tri.tolist(),all_triangles=True);return [(i,j) for i,j in garment.overlap(tree) if triangle_crosses([Vector(v) for v in x[tri[i]]],[Vector(v) for v in skin[skin_faces[j]]])]
    before=None
    for iteration in range(iterations):
        pairs=crossings()
        if before is None:before=len(pairs)
        if not pairs:history.append({'iteration':iteration,'crossings':0});break
        active=np.unique(tri[np.array([p[0] for p in pairs])]);step=np.zeros((n,3));weight=np.zeros(n)
        # Actual crossing planes, including triangle-interior crossings.
        for i,j in pairs:
            ids=tri[i];normal=normals[j];gap=(x[ids]-skin[skin_faces[j,0]])@normal;depth=np.maximum(0.,margin-gap);take=(depth>0)&(~fixed[ids]);selected=ids[take]
            np.add.at(step,selected,depth[take,None]*normal);np.add.at(weight,selected,1.)
        valid=weight>0;step[valid]/=weight[valid,None]
        # Confirm deep vertices with multi-ray votes; nearest plane alone can
        # misclassify an exterior point near an open cut or a bent limb.
        for i in active:
            if fixed[i]:continue
            q,normal,j,distance=tree.find_nearest(Vector(x[i]))
            if q is None or distance>.08:continue
            signed=float(np.dot(x[i]-q,normal))
            if signed<-.00002 and inside_votes(tree,Vector(x[i])):step[i]=np.array(q)+np.array(normal)*margin-x[i];valid[i]=True
        length=np.linalg.norm(step,axis=1);step*=np.minimum(1.,.006/np.maximum(length,1e-14))[:,None];x+=step;sticky|=valid;sticky[fixed]=False
        # Extend displacement smoothly over each connected clothing piece.
        # Preserve contact-anchor magnitudes rather than averaging them away.
        displacement=x-rest
        for c,ids in groups.items():
            anchors=ids[sticky[ids]]
            if not len(anchors):continue
            kd=KDTree(len(anchors))
            for i in anchors:kd.insert(Vector(rest[i]),int(i))
            kd.balance()
            for i in ids[~sticky[ids]&~fixed[ids]]:
                near=kd.find_n(Vector(rest[i]),min(8,len(anchors)));distance=near[0][2]
                if distance>.07:continue
                indices=[v[1] for v in near];weights=np.exp(-np.array([v[2] for v in near])**2/.025**2);weights/=weights.sum();x[i]=rest[i]+(weights@displacement[indices])*np.exp(-distance**2/.025**2)
        delta=x-rest;length=np.linalg.norm(delta,axis=1)
        if np.any(length>max_displacement):
            delta*=np.minimum(1.,max_displacement/np.maximum(length,1e-14))[:,None];x=rest+delta
        x[fixed]=rest[fixed];row={'iteration':iteration,'crossings':len(pairs),'max_displacement_m':float(np.linalg.norm(x-rest,axis=1).max()),'active_vertices':len(active)};history.append(row)
        if progress:progress(row)
    final=crossings();lengths=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1);ratio=lengths/np.maximum(rest_lengths,1e-12);output=points+(x-rest)[inverse]
    return output,{'status':'STATIC_SURFACE_CONTACT_CLEAR' if not final else 'STATIC_SURFACE_CONTACT_NOT_CLEAR','before_crossings':before,'after_crossings':len(final),'max_displacement_m':float(np.linalg.norm(output-points,axis=1).max()),'edge_ratio_quantiles':np.quantile(ratio,[0,.01,.5,.99,1]).tolist(),'seam_clusters':n,'source_vertices':len(points),'locked_vertices':int(fixed.sum()),'history':history,'scope':'Static garment/body triangles only; not self/layer collision or dynamic cloth acceptance'}
