"""Rotation-aware cloth blending and welded, bounded-strain post constraints."""
import numpy as np,math
from mathutils import Matrix,Quaternion


def rotation_blend(reference,physical,factors,pins,*,previous_rotation=None,return_rotation=False):
    """Blend deformation in aligned frames, avoiding 180-degree cancellation."""
    fixed=pins>.999999;center=reference[fixed].mean(axis=0);r=reference-center;p=physical-center;u,_,vt=np.linalg.svd(r.T@p);rotation=u@vt
    if np.linalg.det(rotation)<0:u[:,-1]*=-1;rotation=u@vt
    q=Matrix(rotation.T.tolist()).to_quaternion()
    if previous_rotation is not None:
        if q.dot(previous_rotation)<0:q=Quaternion(tuple(-value for value in q))
        change=previous_rotation.rotation_difference(q).angle
        if change>math.radians(20):q=previous_rotation.slerp(q,math.radians(20)/change)
        rotation=np.array(q.to_matrix()).T
    aligned=p@rotation.T;f=np.clip(factors*(1-pins),0,1);shape=r*(1-f[:,None])+aligned*f[:,None];out=np.empty_like(shape);vector=np.array([q.x,q.y,q.z]);size=np.linalg.norm(vector);angle=2*math.atan2(size,float(q.w));axis=vector/max(size,1e-12)
    # Preserve quaternion hemisphere history. Shortest-arc interpolation from
    # identity otherwise flips direction when the fitted rotation crosses pi.
    for i,value in enumerate(f):
        fractional=Quaternion(tuple(axis),angle*float(value)) if size>1e-10 else Quaternion((1,0,0,0));out[i]=np.array(fractional.to_matrix())@shape[i]+center
    out[fixed]=reference[fixed];return (out,q) if return_rotation else out


def project_strain(points,rest,edges,triangles,pins,anchors,*,iterations=90,min_ratio=.75,max_ratio=1.25,min_area_ratio=.45):
    """Jacobi distance/area constraints; fixed cuff points remain exact."""
    x=points.copy();mass=(1-np.clip(pins,0,1))**2;fixed=pins>.999999;a,b=edges.T;length0=np.linalg.norm(rest[b]-rest[a],axis=1);ta,tb,tc=triangles.T;cross0=np.cross(rest[tb]-rest[ta],rest[tc]-rest[ta]);area0=np.linalg.norm(cross0,axis=1)*.5;fallback=cross0/np.maximum(np.linalg.norm(cross0,axis=1)[:,None],1e-12)
    for _ in range(iterations):
        delta=x[b]-x[a];length=np.linalg.norm(delta,axis=1);desired=np.clip(length,length0*min_ratio,length0*max_ratio);denom=mass[a]+mass[b];correction=delta*((length-desired)/np.maximum(length,1e-12)/np.maximum(denom,1e-12))[:,None];active=np.abs(length-desired)>1e-9;correction[~active]=0.;total=np.zeros_like(x);count=np.zeros(len(x));np.add.at(total,a,correction*mass[a,None]);np.add.at(total,b,-correction*mass[b,None]);np.add.at(count,a,active);np.add.at(count,b,active);x+=total/np.maximum(count[:,None],1)
        normal=np.cross(x[tb]-x[ta],x[tc]-x[ta]);size=np.linalg.norm(normal,axis=1);normal=np.where((size>1e-10)[:,None],normal/np.maximum(size[:,None],1e-12),fallback);area=size*.5;deficit=np.maximum(area0*min_area_ratio-area,0);ga=.5*np.cross(x[tb]-x[tc],normal);gb=.5*np.cross(x[tc]-x[ta],normal);gc=.5*np.cross(x[ta]-x[tb],normal);denom=mass[ta]*np.sum(ga*ga,axis=1)+mass[tb]*np.sum(gb*gb,axis=1)+mass[tc]*np.sum(gc*gc,axis=1);lam=deficit/np.maximum(denom,1e-14);total=np.zeros_like(x);count[:]=0
        for ids,gradient in ((ta,ga),(tb,gb),(tc,gc)):
            np.add.at(total,ids,gradient*(mass[ids]*lam)[:,None]);np.add.at(count,ids,deficit>1e-12)
        x+=total/np.maximum(count[:,None],1);x[fixed]=anchors[fixed]
    return x
