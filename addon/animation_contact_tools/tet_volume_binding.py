"""Contained barycentric embedding of display vertices in a physical volume."""
import numpy as np


def bind_volume(points,vertices,tetrahedra,tolerance=1e-5):
    points=np.asarray(points,dtype=float);vertices=np.asarray(vertices,dtype=float);tetrahedra=np.asarray(tetrahedra,dtype=int)
    if points.ndim!=2 or points.shape[1]!=3 or vertices.ndim!=2 or vertices.shape[1]!=3 or tetrahedra.ndim!=2 or tetrahedra.shape[1]!=4 or tolerance<0 or not np.all(np.isfinite(points)) or not np.all(np.isfinite(vertices)):
        raise ValueError('Finite 3D points and vertices and four-index tetrahedra required')
    if not len(points) or not len(tetrahedra) or np.min(tetrahedra)<0 or np.max(tetrahedra)>=len(vertices):raise ValueError('Invalid volume topology or empty point set')
    t=vertices[tetrahedra];inverse=np.linalg.inv(np.stack((t[:,1]-t[:,0],t[:,2]-t[:,0],t[:,3]-t[:,0]),axis=2));indices=[];weights=[];minimum=1.
    for begin in range(0,len(points),128):
        q=np.einsum('tij,vtj->vti',inverse,points[begin:begin+128,None,:]-t[None,:,0]);b=np.concatenate((1-q.sum(2,keepdims=True),q),axis=2);score=b.min(2);chosen=score.argmax(1);best=score[np.arange(len(chosen)),chosen];minimum=min(minimum,float(best.min()))
        if np.any(best < -tolerance):raise ValueError(f'Display points lie outside physical volume ({int((best < -tolerance).sum())} in chunk); rebuild the legal rest envelope')
        indices.extend(chosen.tolist());weights.extend(b[np.arange(len(chosen)),chosen].tolist())
    weights=np.maximum(np.asarray(weights),0.);weights/=weights.sum(1)[:,None];indices=np.asarray(indices,dtype=int);reconstructed=np.einsum('vi,vij->vj',weights,vertices[tetrahedra[indices]]);error=float(np.max(np.linalg.norm(reconstructed-points,axis=1)))
    return dict(tetrahedron_indices=indices,weights=weights,vertex_indices=tetrahedra[indices],minimum_unclamped_barycentric=minimum,reconstruction_error_m=error)


def deform_volume(binding,vertices):
    vertices=np.asarray(vertices,dtype=float)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or not np.all(np.isfinite(vertices)):raise ValueError('Finite volume positions required')
    return np.einsum('vi,vij->vj',binding['weights'],vertices[binding['vertex_indices']])
