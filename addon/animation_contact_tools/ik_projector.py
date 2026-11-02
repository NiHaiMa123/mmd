"""Experimental bounded horizontal IK-target correction for leg contacts.

Explicitly permits footprint changes, so this is never silently enabled for a
planted-foot motion. A gait/contact-phase adapter must approve such changes.
"""
import numpy as np
import bpy
from mathutils import Vector
from .surface import coords,audit_frame
from .projector import FrameProjector

class FootProjector:
    constraints=FrameProjector.constraints
    features=staticmethod(FrameProjector.features)

    def __init__(self,mesh,arm,profile,parts,controls,max_offset_m=.04):
        self.mesh,self.arm,self.profile,self.parts=mesh,arm,profile,parts;self.units=profile.get('units_to_m',1.)
        self.bones=[arm.pose.bones[n] for n in controls];self.n=2*len(self.bones);self.limit=max_offset_m;self.movable_prefixes=('leg',)
        self.target_regions=set(('torso','head','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'))

    def capture(self):self.base=[b.matrix.copy() for b in self.bones]

    def bounded(self,x):
        x=np.asarray(x).copy()
        for j in range(0,self.n,2):
            size=np.linalg.norm(x[j:j+2])
            if size>self.limit:x[j:j+2]*=self.limit/size
        return x

    def apply(self,x):
        transform=self.arm.matrix_world.inverted().to_3x3()
        for j,(b,matrix) in enumerate(zip(self.bones,self.base)):
            target=matrix.copy();target.translation+=transform@Vector((x[2*j]/self.units,x[2*j+1]/self.units,0));b.matrix=target
        self.arm.update_tag();bpy.context.view_layer.update()

    def solve(self,initial=None,iterations=30):
        x=self.bounded(np.zeros(self.n) if initial is None else initial);history=[];self.apply(x)
        for it in range(iterations):
            audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000);co=coords(self.mesh)*self.units;cs=self.constraints(audit,co)
            if not cs:break
            normal=np.array([c[-2] for c in cs]);rhs=self.profile['clearance_m']-np.array([c[-1] for c in cs]);base=self.features(co,cs);jac=np.zeros((len(cs),self.n))
            for j in range(self.n):
                pert=x.copy();pert[j]+=.0005;self.apply(pert);jac[:,j]=np.einsum('ij,ij->i',self.features(coords(self.mesh)*self.units,cs)-base,normal)/.0005
            self.apply(x);step=np.linalg.solve(jac.T@jac+np.eye(self.n)*.001,jac.T@rhs-.002*x)
            for j in range(0,self.n,2):
                size=np.linalg.norm(step[j:j+2])
                if size>.005:step[j:j+2]*=.005/size
            accepted=False;previous=float(np.sum(np.maximum(rhs,0)**2))
            for factor in (1,.5,.25,.1):
                proposal=self.bounded(x+factor*step);self.apply(proposal);change=np.einsum('ij,ij->i',self.features(coords(self.mesh)*self.units,cs)-base,normal)
                if float(np.sum(np.maximum(rhs-change,0)**2))<previous-1e-12:x=proposal;accepted=True;break
            history.append({'iteration':it,'accepted':accepted})
            if not accepted:break
        self.apply(x);audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000);rows=[r for r in audit['pairs'] if r['pair'][0].startswith('leg')]
        remaining=sum(r['triangle_crossings']+r['contained_samples'] for r in rows)
        return x,{'status':'LEG_DISCRETE_PASS' if not remaining else 'LEG_UNRESOLVED','remaining':remaining,'max_foot_offset_m':max(float(np.linalg.norm(x[j:j+2])) for j in range(0,self.n,2)),'history':history,'changes_footprints':True}
