"""Opposed rotations must not flatten the sleeve during shape blending."""
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.sleeve_shape_constraints import rotation_blend,project_strain
rest=np.array([(0,0,0),(0,0,.1),(1,0,0),(1,.2,.1),(.5,.2,.1)],dtype=float);physical=rest@np.diag([-1,-1,1]);pins=np.array([1,1,0,0,0.]);f=np.full(len(rest),.5);result=rotation_blend(rest,physical,f,pins);linear=(rest+physical)*.5
assert np.linalg.norm(linear[2]-linear[3])<.11
assert abs(np.linalg.norm(result[2]-result[3])-np.linalg.norm(rest[2]-rest[3]))<1e-6
assert np.max(np.abs(result[:2]-rest[:2]))==0
previous=None;last=None;largest_step=0.
for degrees in range(170,191):
 angle=np.deg2rad(degrees);matrix=np.array(((np.cos(angle),-np.sin(angle),0),(np.sin(angle),np.cos(angle),0),(0,0,1)));pose,q=rotation_blend(rest,rest@matrix.T,f,pins,previous_rotation=previous,return_rotation=True)
 if last is not None:largest_step=max(largest_step,float(np.linalg.norm(pose-last,axis=1).max()))
 previous=q;last=pose
assert largest_step<.02,largest_step
tri=np.array([(0,2,3),(0,3,1),(2,4,3)]);edges=np.array(sorted({tuple(sorted(e)) for t in tri for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0]))}));broken=rest.copy();broken[2]=(4,0,0);broken[3]=(.1,.001,.001);fixed=project_strain(broken,rest,edges,tri,pins,rest,iterations=300);ratio=np.linalg.norm(fixed[edges[:,1]]-fixed[edges[:,0]],axis=1)/np.linalg.norm(rest[edges[:,1]]-rest[edges[:,0]],axis=1)
assert ratio.max()<1.5 and ratio.min()>.5,ratio
assert np.max(np.abs(fixed[:2]-rest[:2]))==0
print('SLEEVE_ROTATION_BLEND_CONTRACT_OK',float(ratio.min()),float(ratio.max()))
