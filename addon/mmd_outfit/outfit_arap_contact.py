"""Static ARAP garment fitting, with actual vertex/triangle contact queries."""
import json,subprocess
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri
from mathutils.bvhtree import BVHTree
from .motion_contact import triangle_crosses,inside_votes


def intersection_midpoint(first,second):
    points=[]
    for a,b in ((first,second),(second,first)):
        for i in range(3):
            origin=Vector(a[i]);direction=Vector(a[(i+1)%3])-origin
            if direction.length_squared<1e-20:continue
            hit=intersect_ray_tri(*(Vector(v) for v in b),direction,origin,True)
            if hit is None:continue
            t=(hit-origin).dot(direction)/direction.length_squared
            if -1e-6<=t<=1+1e-6 and not any((hit-v).length<1e-6 for v in points):points.append(hit)
    return np.mean([list(v) for v in points],axis=0) if points else np.mean(first,axis=0)


def fit_surface_arap(points,faces,skin,skin_faces,*,workspace,runtime,worker,locked=None,margin=.0015,iterations=35,max_displacement=.10,progress=None):
    workspace=Path(workspace);workspace.mkdir(parents=True,exist_ok=True);points=np.asarray(points,dtype=float);skin=np.asarray(skin,dtype=float);faces=np.asarray(faces,dtype=int);skin_faces=np.asarray(skin_faces,dtype=int);_,inverse=np.unique(np.rint(points/1e-6).astype(np.int64),axis=0,return_inverse=True);n=int(inverse.max())+1;rest=np.zeros((n,3));np.add.at(rest,inverse,points);rest/=np.bincount(inverse)[:,None];tri=inverse[faces];tri=tri[np.array([len(set(f))==3 for f in tri])];x=rest.copy();fixed=np.zeros(n,dtype=bool)
    if locked is not None:np.logical_or.at(fixed,inverse,locked)
    edges=np.unique(np.sort(np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])),axis=1),axis=0);length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1);body_tree=BVHTree.FromPolygons(skin.tolist(),skin_faces.tolist(),all_triangles=True);normal=np.cross(skin[skin_faces[:,1]]-skin[skin_faces[:,0]],skin[skin_faces[:,2]]-skin[skin_faces[:,0]]);normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-14);history=[];before=None;remaining_inside=[];previous_active=np.array([],dtype=int);contact_pool={}
    for iteration in range(iterations):
        tree=BVHTree.FromPolygons(x.tolist(),tri.tolist(),all_triangles=True);pairs=[(i,j) for i,j in tree.overlap(body_tree) if triangle_crosses([Vector(v) for v in x[tri[i]]],[Vector(v) for v in skin[skin_faces[j]]])]
        if before is None:before=len(pairs)
        ids=np.arange(n) if iteration%5==0 else np.unique(np.r_[previous_active,tri[np.array([i for i,j in pairs],dtype=int)].reshape(-1)]);rows=[];cols=[];values=[];bound=[];inside=[]
        for i in ids:
            if fixed[i]:continue
            q,norm,j,distance=body_tree.find_nearest(Vector(x[i]))
            if q is None or distance>.08:continue
            signed=float(np.dot(x[i]-q,norm))
            if signed<-.00001 and inside_votes(body_tree,Vector(x[i])):
                contact_pool[('vertex',int(i),int(j))]=([(int(i),np.array(norm))],float(np.dot(q,norm))+margin);inside.append(i)
        for i,j in pairs:
            ids_face=tri[i];a,b,c=x[ids_face];q=intersection_midpoint(x[ids_face],skin[skin_faces[j]]);uv=np.linalg.lstsq(np.column_stack((b-a,c-a)),q-a,rcond=None)[0];bary=np.maximum(0.,[1-uv.sum(),uv[0],uv[1]]);bary/=max(sum(bary),1e-12)
            contact_pool[('face',int(i),int(j))]=([(int(v),normal[j]*w) for v,w in zip(ids_face,bary)],float(np.dot(skin[skin_faces[j,0]],normal[j]))+margin)
        # Keep prior unilateral contacts. Dropping a cleared row lets the ARAP
        # rest prior pull that patch back through skin on the next iteration.
        for terms,value in contact_pool.values():
            row=len(bound)
            for vertex,vector in terms:rows.extend([row]*3);cols.extend([vertex*3,vertex*3+1,vertex*3+2]);values.extend(vector)
            bound.append(value)
        remaining_inside=inside;previous_active=np.unique(np.r_[inside,tri[np.array([i for i,j in pairs],dtype=int)].reshape(-1)]).astype(int)
        if not pairs and not inside:history.append({'iteration':iteration,'crossings':0,'inside_vertices':0});break
        payload=workspace/'constraints.npz';result=workspace/'arap_step.npz';np.savez_compressed(payload,rest=rest,current=x,edges=edges,rows=np.array(rows,dtype=int),cols=np.array(cols,dtype=int),values=np.array(values),bound=np.array(bound),locked=fixed)
        run=subprocess.run([str(runtime),str(worker),'--input',str(payload),'--output',str(result)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace')[-3000:])
        with np.load(result) as data:x=data['points'].copy();violation=float(data['max_constraint_violation']);nonconvergence=data['cg_nonconvergence'].tolist()
        delta=x-rest;movement=np.linalg.norm(delta,axis=1);x=rest+delta*np.minimum(1.,max_displacement/np.maximum(movement,1e-12))[:,None];row={'iteration':iteration,'crossings':len(pairs),'inside_vertices':len(inside),'constraint_violation_m':violation,'max_displacement_m':float(np.linalg.norm(x-rest,axis=1).max()),'cg_nonconvergence':nonconvergence};history.append(row)
        if progress:progress(row)
        (workspace/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    tree=BVHTree.FromPolygons(x.tolist(),tri.tolist(),all_triangles=True);pairs=[(i,j) for i,j in tree.overlap(body_tree) if triangle_crosses([Vector(v) for v in x[tri[i]]],[Vector(v) for v in skin[skin_faces[j]]])];ratio=np.linalg.norm(x[edges[:,0]]-x[edges[:,1]],axis=1)/np.maximum(length,1e-12)
    return points+(x-rest)[inverse],{'status':'STATIC_SURFACE_CONTACT_CLEAR' if not pairs and not remaining_inside else 'STATIC_SURFACE_CONTACT_NOT_CLEAR','method':'local/global ARAP with unilateral vertex and barycentric triangle contacts','before_crossings':before,'after_crossings':len(pairs),'last_inside_vertices':len(remaining_inside),'max_displacement_m':float(np.linalg.norm(x-rest,axis=1).max()),'edge_ratio_quantiles':np.quantile(ratio,[0,.01,.5,.99,1]).tolist(),'locked_vertices':int(fixed.sum()),'history':history,'scope':'Static garment/body fit; dynamic, self and layer contacts require independent checks'}
