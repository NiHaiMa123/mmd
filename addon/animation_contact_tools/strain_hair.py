"""Evaluated-skin bone projection with an explicit relative edge-strain loss.

Quasi-static contact repair, no dynamics/CCD or full surface guarantee.
"""
from collections import defaultdict
import numpy as np
from .hair_projector import HairProjector
from .surface import coords,audit_frame

class StrainHairProjector(HairProjector):
    def capture(self):
        super().capture();co=coords(self.mesh)*self.units;hair=set(self.parts['ids']['hair_root']+self.parts['ids']['hair_mobile']);edges=np.array([e.vertices[:] for e in self.mesh.data.edges if all(i in hair for i in e.vertices)],dtype=int);length=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);valid=length>.0005;self.edges=edges[valid];self.lengths=length[valid]

    def strain(self,co):return np.linalg.norm(co[self.edges[:,0]]-co[self.edges[:,1]],axis=1)/self.lengths

    def solve(self,initial=None,iterations=50,preferred=None):
        x=self.bounded(np.zeros(self.n) if initial is None else initial);history=[];self.apply(x);scale=self.profile.get('hair_strain_scale_m',.03);tolerance=self.profile.get('hair_strain_tolerance',.015)
        preferred=np.zeros(self.n) if preferred is None else np.asarray(preferred)
        analytic=None;analytic_check=None
        if self.profile.get('hair_analytic_jacobian',False):
            from .hair_skin_jacobian import HairSkinJacobian
            analytic=HairSkinJacobian(self)
        for iteration in range(iterations):
            audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=True,cap=3000,return_witness_pairs=True);co=coords(self.mesh)*self.units;cs=self.constraints(audit,co);ratio=self.strain(co);error=ratio-1
            total=sum(r['triangle_crossings'] for r in audit['pairs'] if r['pair'][0].startswith('hair') and r['pair'][1] in self.targets)
            if total==0 and ratio.max()<1.10 and ratio.min()>.90:break
            if not cs and ratio.max()<1.10 and ratio.min()>.90:break
            importance=defaultdict(float)
            for im,wm,it,wt,n,d in cs:
                for i in im:
                    for j,w in self.affected[i].items():importance[j]+=w*(self.profile['clearance_m']-d)
            strain_ids=np.flatnonzero(np.abs(error)>tolerance)
            strain_ids=strain_ids[np.argsort(np.abs(error[strain_ids]))[-350:]]
            for i in self.edges[strain_ids].ravel():
                for j,w in self.affected[i].items():importance[j]+=.002*w
            selected=list(range(len(self.bones))) if analytic else sorted(importance,key=importance.get,reverse=True)[:self.max_active];dofs=[j*3+k for j in selected for k in range(3)]
            normals=np.array([c[-2] for c in cs]).reshape(-1,3);contact_rhs=self.profile['clearance_m']-np.array([c[-1] for c in cs]);base=self.features(co,cs).reshape(-1,3);edge_base=ratio[strain_ids]*scale
            strain_rhs=-(error[strain_ids]-np.clip(error[strain_ids],-tolerance,tolerance))*scale;rhs=np.r_[contact_rhs,strain_rhs];jac=np.zeros((len(rhs),len(dofs)))
            if analytic:
                vertex_ids=sorted({i for c in cs for i in c[0]+c[2]}|set(self.edges[strain_ids].ravel().tolist()));vj,lookup=analytic.vertices(vertex_ids,x)
                if analytic_check is None:
                    top=sorted(importance,key=importance.get,reverse=True)[:2];analytic_check=analytic.verify(x,vertex_ids,[3*j+k for j in top for k in range(3)])
                for k,(im,wm,it,wt,normal,signed) in enumerate(cs):
                    differential=np.tensordot(wm,vj[lookup[im]],axes=(0,0))-np.tensordot(wt,vj[lookup[it]],axes=(0,0));jac[k]=differential@normal
                if len(strain_ids):
                    edge=self.edges[strain_ids];direction=co[edge[:,0]]-co[edge[:,1]];direction/=np.linalg.norm(direction,axis=1)[:,None];jac[len(cs):]=np.einsum('enj,ej->en',vj[lookup[edge[:,0]]]-vj[lookup[edge[:,1]]],direction)/self.lengths[strain_ids,None]*scale
            else:
                for j,dof in enumerate(dofs):
                    pert=x.copy();pert[dof]+=.001;self.apply(pert);new=coords(self.mesh)*self.units;jac[:len(cs),j]=np.einsum('ij,ij->i',self.features(new,cs)-base,normals)/.001;jac[len(cs):,j]=(self.strain(new)[strain_ids]*scale-edge_base)/.001
            self.apply(x);step=np.linalg.solve(jac.T@jac+np.eye(len(dofs))*.0003,jac.T@rhs-.0002*(x[dofs]-preferred[dofs]))
            for j in range(0,len(step),3):
                size=np.linalg.norm(step[j:j+3])
                if size>np.radians(2):step[j:j+3]*=np.radians(2)/size
            def score(c,new_ratio):return float(np.maximum(c,0)@np.maximum(c,0)+np.sum((np.maximum(np.abs(new_ratio-1)-tolerance,0)*scale)**2))
            previous=score(contact_rhs,ratio);accepted=False
            for factor in (1,.5,.25,.1,.025):
                proposal=x.copy();proposal[dofs]+=step*factor;proposal=self.bounded(proposal);self.apply(proposal);new=coords(self.mesh)*self.units;new_ratio=self.strain(new);change=np.einsum('ij,ij->i',self.features(new,cs)-base,normals)
                if score(contact_rhs-change,new_ratio)<previous-1e-12:x=proposal;accepted=True;break
            history.append({'iteration':iteration,'target_crossings':total,'constraints':len(cs),'strain_constraints':len(strain_ids),'edge_ratio_max':float(ratio.max()),'accepted':accepted})
            if iteration%10==0:print('STRAIN_HAIR_ITER',iteration,total,float(ratio.max()),flush=True)
            if not accepted:break
        self.apply(x);co=coords(self.mesh)*self.units;ratio=self.strain(co);audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=True,cap=4000)
        target=[r for r in audit['pairs'] if r['pair'][0].startswith('hair') and r['pair'][1] in self.targets];other=[r for r in audit['pairs'] if r['pair'][0].startswith('hair') and r['pair'][1] not in self.targets];count=sum(r['triangle_crossings'] for r in target)
        return x,{'status':'TARGET_SURFACE_AND_STRAIN_PASS' if count==0 and ratio.max()<1.10 and ratio.min()>.90 else 'HAIR_UNRESOLVED','remaining_target_crossings':count,'remaining_other_crossings':sum(r['triangle_crossings'] for r in other),'target_regions':sorted(self.targets),'edge_ratio_max':float(ratio.max()),'edge_ratio_min':float(ratio.min()),'edge_ratio_p99':float(np.percentile(ratio,99)),'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in target+other if r['triangle_crossings']],'max_delta_degrees':float(max(np.linalg.norm(x[j:j+3]) for j in range(0,self.n,3))*180/np.pi),'history':history,'analytic_jacobian_check':analytic_check}
