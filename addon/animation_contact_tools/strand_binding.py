"""Rest-exact, finite-width mesh binding to a sampled guide curve.

Parallel transported frames preserve each cross-section. This is a deformation
adapter, not a collision or inextensibility guarantee for the mapped surface.
"""
import numpy as np


def normalize(x):return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-12)


def frames(points,root_normal):
    points=np.asarray(points);t=np.empty_like(points);t[0]=points[1]-points[0];t[-1]=points[-1]-points[-2];t[1:-1]=points[2:]-points[:-2];t=normalize(t)
    n=np.empty_like(t);n[0]=normalize(np.asarray(root_normal)-t[0]*np.dot(root_normal,t[0]))
    if np.linalg.norm(n[0])<.5:raise ValueError('Root normal is parallel to guide tangent')
    for i in range(1,len(points)):
        a,b=t[i-1],t[i];v=np.cross(a,b);c=np.dot(a,b)
        if c<-.999:raise ValueError('Guide folds through 180 degrees; frame transport is ambiguous')
        candidate=n[i-1]+np.cross(v,n[i-1])+np.cross(v,np.cross(v,n[i-1]))/(1+c)
        n[i]=normalize(candidate-b*np.dot(candidate,b))
    return t,n


def sample_frames(points,root_normal,segment,factor):
    t,n=frames(points,root_normal);u=factor[:,None];t=normalize(t[segment]*(1-u)+t[segment+1]*u);n=n[segment]*(1-u)+n[segment+1]*u;n=normalize(n-t*np.sum(n*t,axis=1)[:,None]);b=np.cross(t,n)
    return np.stack((t,n,b),axis=2)


def bind_vertices(vertices,guide,root_normal):
    vertices=np.asarray(vertices);guide=np.asarray(guide);d=guide[1:]-guide[:-1];relative=vertices[:,None,:]-guide[None,:-1,:]
    all_u=np.clip(np.einsum('vse,se->vs',relative,d)/np.maximum(np.sum(d*d,axis=1),1e-16),0,1);q=guide[None,:-1,:]+all_u[:,:,None]*d[None,:,:];segment=np.argmin(np.sum((vertices[:,None,:]-q)**2,axis=2),axis=1);factor=all_u[np.arange(len(vertices)),segment];centre=q[np.arange(len(vertices)),segment];frame=sample_frames(guide,root_normal,segment,factor);offset=np.einsum('vji,vj->vi',frame,vertices-centre)
    return {'segment':segment,'factor':factor,'offset':offset,'root_normal':np.asarray(root_normal),'rest_guide':guide.copy()}


def deform_vertices(binding,guide,root_normal):
    i,u=binding['segment'],binding['factor'][:,None];guide=np.asarray(guide);centre=guide[i]*(1-u)+guide[i+1]*u
    return centre+np.einsum('vij,vj->vi',sample_frames(guide,root_normal,i,binding['factor']),binding['offset'])


def conservative_radii(binding,point_count,padding=.001):
    radii=np.zeros(point_count);distance=np.linalg.norm(binding['offset'],axis=1)
    np.maximum.at(radii,binding['segment'],distance);np.maximum.at(radii,binding['segment']+1,distance)
    return np.maximum(radii+padding,.0015)


def slerp(a,b,t):
    a=normalize(np.asarray(a));b=normalize(np.asarray(b));dot=np.sum(a*b,axis=1);b=np.where((dot<0)[:,None],-b,b);dot=np.clip(np.abs(dot),0,1);angle=np.arccos(dot);s=np.maximum(np.sin(angle),1e-12);t=np.asarray(t)
    curved=(np.sin((1-t)*angle)[:,None]*a+np.sin(t*angle)[:,None]*b)/s[:,None]
    return normalize(np.where((dot>.9995)[:,None],a*(1-t[:,None])+b*t[:,None],curved))


def rotate_vectors(q,v):
    xyz=q[:,1:];return v+2*np.cross(xyz,np.cross(xyz,v)+q[:,:1]*v)


def bind_rod_vertices(vertices,guide,quaternions,segment,factor):
    guide=np.asarray(guide);segment=np.asarray(segment);factor=np.asarray(factor);q=slerp(quaternions[segment],quaternions[segment+1],factor);inv=q.copy();inv[:,1:]*=-1;centre=guide[segment]*(1-factor[:,None])+guide[segment+1]*factor[:,None]
    return {'segment':segment,'factor':factor,'rod_offset':rotate_vectors(inv,np.asarray(vertices)-centre)}


def deform_rod_vertices(binding,guide,quaternions):
    i,u=binding['segment'],binding['factor'];q=slerp(quaternions[i],quaternions[i+1],u);centre=guide[i]*(1-u[:,None])+guide[i+1]*u[:,None]
    return centre+rotate_vectors(q,binding['rod_offset'])
