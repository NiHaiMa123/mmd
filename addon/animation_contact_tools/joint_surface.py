"""Experimental bounded local skin correction for joint-induced folds.

This is distinct from moving a limb around another body part. It must not be
used to shrink a whole body through an obstacle or replace gesture semantics.
"""
from collections import defaultdict
import numpy as np
from .surface import audit_frame,coords
from .projector import FrameProjector

class JointSurfaceProjector:
    constraints=FrameProjector.constraints

    def __init__(self,mesh,arm,profile,parts,mover_roles=('leg.L','leg.R'),target_roles=('torso',),max_offset_m=.008):
        self.mesh,self.arm,self.profile,self.parts=mesh,arm,dict(profile),parts
        self.profile['pairs']=[(a,b) for a in mover_roles for b in target_roles]
        self.profile['clearance_m']=.0006;self.movable_prefixes=tuple(mover_roles);self.units=profile.get('units_to_m',1.);self.max_offset=max_offset_m
        self.target_regions=set(target_roles)
        self.movable=set(i for role in mover_roles for i in parts['ids'][role])-set(i for role in target_roles for i in parts['ids'][role])
        self.neighbors=defaultdict(set)
        for edge in mesh.data.edges:
            a,b=edge.vertices
            self.neighbors[a].add(b);self.neighbors[b].add(a)

    def solve(self,iterations=30):
        base=coords(self.mesh)*self.units;co=base.copy();history=[];initial=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000,coordinates_m=co)
        active=set(i for r in initial['pairs'] for i in r['moving_vertices'])&self.movable
        for _ in range(4):active|={j for i in list(active) for j in self.neighbors[i] if j in self.movable}
        for iteration in range(iterations):
            audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000,coordinates_m=co);count=audit['ordinary_crossings']+audit['ordinary_contained_samples']
            if not count:break
            cs=self.constraints(audit,co)
            if not cs:break
            old=co.copy()
            for im,wm,it,wt,normal,signed in cs:
                weights=defaultdict(float)
                for i,w in zip(im,wm):weights[i]+=w
                for i,w in zip(it,wt):weights[i]-=w
                weights={i:w for i,w in weights.items() if i in active}
                denominator=sum(w*w for w in weights.values())
                if denominator<1e-12:continue
                initial_feature=np.asarray(wm)@old[im]-np.asarray(wt)@old[it]
                feature=np.asarray(wm)@co[im]-np.asarray(wt)@co[it]
                gap=self.profile['clearance_m']-signed-float((feature-initial_feature)@normal)
                if gap<=0:continue
                for i,w in weights.items():co[i]+=normal*w*gap/denominator*.7
            # Regularize the displacement field, not the original surface, so
            # this does not globally smooth anatomy or change the rest model.
            displacement=co-base;regularized=displacement.copy()
            for i in active:
                neighbors=list(self.neighbors[i])
                if neighbors:regularized[i]=.86*displacement[i]+.14*displacement[neighbors].mean(0)
            lengths=np.linalg.norm(regularized,axis=1);large=lengths>self.max_offset;regularized[large]*=(self.max_offset/lengths[large])[:,None];co=base+regularized
            history.append({'iteration':iteration,'crossings':count,'constraints':len(cs),'max_step_m':float(np.linalg.norm(co-old,axis=1).max())})
        final=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000,coordinates_m=co)
        edges=np.array([edge.vertices[:] for edge in self.mesh.data.edges if any(i in active for i in edge.vertices)]);length=np.linalg.norm(base[edges[:,0]]-base[edges[:,1]],axis=1);valid=length>.0005
        ratio=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1)[valid]/length[valid] if len(edges) else np.array([1.])
        passed=not(final['ordinary_crossings'] or final['ordinary_contained_samples']) and float(ratio.max())<1.25 and float(ratio.min())>.8
        return co-base,{'status':'JOINT_DISCRETE_WITH_STRAIN_PASS' if passed else 'JOINT_SURFACE_UNRESOLVED_OR_STRAIN_FAIL','before':initial['ordinary_crossings'],'remaining':final['ordinary_crossings'],'max_offset_m':float(np.linalg.norm(co-base,axis=1).max()),'active_vertices':len(active),'edge_ratio_p99':float(np.percentile(ratio,99)),'edge_ratio_max':float(ratio.max()),'edge_ratio_min':float(ratio.min()),'history':history}
