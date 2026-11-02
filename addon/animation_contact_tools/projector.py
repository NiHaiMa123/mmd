"""Bounded evaluated-skin Jacobian projection for ordinary arm collisions.

No global no-intersection guarantee: independent surface checks decide success.
The solver does not accept bilateral contact as an avoidance objective.
"""
import math
import numpy as np
import bpy
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,intersect_ray_tri
from .surface import coords,audit_frame

def exp_quat(v):
    angle=float(np.linalg.norm(v));return Quaternion(Vector(v)/angle,angle) if angle>1e-12 else Quaternion()

class FrameProjector:
    def __init__(self,mesh,arm,profile,parts,controls,limit_degrees=20):
        self.mesh,self.arm,self.profile,self.parts=mesh,arm,profile,parts
        self.movable_prefixes=('arm','hand')
        self.target_regions=set(('torso','head','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R'))|set(profile.get('extra_contact_targets',[]))
        if parts.get('missing_body_mapping',0):raise ValueError('Unmapped body surface: complete the rig profile before solving')
        if not parts['faces'].get('torso') or not parts['faces'].get('head'):raise ValueError('The current projector requires explicit torso and head surfaces')
        self.controls=controls;preserve=profile.get('preserve_wrist_orientation',True)
        self.bones=[arm.pose.bones[n] for chain in controls for n in (chain[:2] if preserve else chain)]
        self.units=float(profile.get('units_to_m',1.))
        if self.units<=0:raise ValueError('units_to_m must be positive')
        self.wrists=[arm.pose.bones[chain[2]] for chain in controls] if preserve else []
        if any(b.rotation_mode!='QUATERNION' for b in self.bones+self.wrists):raise ValueError('This adapter requires quaternion control channels')
        self.limit=math.radians(limit_degrees);self.n=len(self.bones)*3

    def bounded(self,x):
        x=np.asarray(x,dtype=float).copy()
        if x.shape!=(self.n,) or not np.all(np.isfinite(x)):raise ValueError('Invalid control seed')
        for j in range(0,self.n,3):
            size=np.linalg.norm(x[j:j+3])
            if size>self.limit:x[j:j+3]*=self.limit/size
        return x

    def capture(self):
        self.base=[b.rotation_quaternion.copy() for b in self.bones];self.wrist_base=[b.rotation_quaternion.copy() for b in self.wrists]
        self.hand_frames=[b.matrix.copy() for b in self.wrists]

    def apply(self,x):
        for i,b in enumerate(self.bones):b.rotation_quaternion=self.base[i]@exp_quat(x[i*3:i*3+3])
        for b,q in zip(self.wrists,self.wrist_base):b.rotation_quaternion=q
        self.arm.update_tag();bpy.context.view_layer.update()
        for wrist,matrix in zip(self.wrists,self.hand_frames):
            target=matrix.copy();target.translation=wrist.head;wrist.matrix=target
        self.arm.update_tag();bpy.context.view_layer.update()

    def constraints(self,audit,co):
        world=co.tolist();result=[];trees={}
        def tree(r):
            if r not in trees:trees[r]=BVHTree.FromPolygons(world,self.parts['faces'][r],all_triangles=True)
            return trees[r]
        basis=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
        for row in audit['pairs']:
            a,b=row['pair']
            if row['classification']!='ordinary_collision' or not a.startswith(self.movable_prefixes) or b not in self.target_regions or not (row['triangle_crossings'] or row.get('contained_samples',0)):continue
            pair_begin=len(result)
            for reverse,indices in [(False,row['moving_vertices']),(True,row['target_vertices'])]:
                target=a if reverse else b
                for i in indices:
                    p=Vector(co[i]);q,n,fi,d=tree(target).find_nearest(p)
                    if q is None or d>.08:continue
                    signed=(p-q).dot(n)
                    if signed>=self.profile['clearance_m']:continue
                    if d>1e-6 and abs(signed)/d<.65:continue
                    tri=self.parts['faces'][target][fi];weights=barycentric_transform(q,*[Vector(co[k]) for k in tri],*basis)
                    if reverse:result.append((list(tri),list(weights),[i],[1.],np.array(-n),float(signed)))
                    else:result.append(([i],[1.],list(tri),list(weights),np.array(n),float(signed)))
            # Keep existing penetrating-vertex rows when they are available.
            # Adding zero-gap witnesses to a deep overlap can oppose those
            # rows on a curved target and stall the legacy projection.
            if len(result)>pair_begin:continue
            # A face can cut through another face while every vertex is
            # outside the nearest surface. Add true edge/triangle intersection
            # witnesses; nearest-vertex constraints alone cannot resolve it.
            for moving,target in row.get('witness_pairs',[]):
                mt=[Vector(co[i]) for i in moving];tt=[Vector(co[i]) for i in target]
                normal=(tt[1]-tt[0]).cross(tt[2]-tt[0])
                if normal.length<1e-12:continue
                normal.normalize();seen=[]
                for source_triangle,other_triangle in ((mt,tt),(tt,mt)):
                    for j in range(3):
                        origin=source_triangle[j];direction=source_triangle[(j+1)%3]-origin
                        if direction.length_squared<1e-20:continue
                        hit=intersect_ray_tri(*other_triangle,direction,origin,True)
                        if hit is None:continue
                        fraction=(hit-origin).dot(direction)/direction.length_squared
                        if not 1e-7<fraction<1-1e-7 or any((hit-old).length<1e-6 for old in seen):continue
                        wm=np.array(barycentric_transform(hit,*mt,*basis));wt=np.array(barycentric_transform(hit,*tt,*basis))
                        if min(wm.min(),wt.min())<-.0001:continue
                        seen.append(hit);gap=float(np.dot(wm@co[moving]-wt@co[target],np.array(normal)))
                        result.append((list(moving),wm.tolist(),list(target),wt.tolist(),np.array(normal),gap))
        result.sort(key=lambda c:c[-1]);return result[:220]

    @staticmethod
    def features(co,cs):
        return np.array([np.asarray(wm)@co[im]-np.asarray(wt)@co[it] for im,wm,it,wt,n,d in cs])

    def solve(self,initial=None,iterations=20,preferred=None):
        frame=float(bpy.context.scene.frame_current_final)
        if any(w['start']<=frame<=w['end'] for w in self.profile.get('protected_windows',[])):
            self.apply(np.zeros(self.n));return np.zeros(self.n),{'status':'DEFERRED_PROTECTED_WINDOW'}
        x=self.bounded(np.zeros(self.n) if initial is None else initial);preferred=self.bounded(np.zeros(self.n) if preferred is None else preferred)
        self.apply(x);history=[]
        for it in range(iterations):
            audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=1000,return_witness_pairs=True);co=coords(self.mesh)*self.units;cs=self.constraints(audit,co)
            total=sum(r['triangle_crossings']+r.get('contained_samples',0) for r in audit['pairs'] if r['classification']=='ordinary_collision')
            if not cs:break
            normals=np.array([c[-2] for c in cs]);gaps=np.array([c[-1] for c in cs]);base=self.features(co,cs);jac=np.zeros((len(cs),self.n));eps=.001
            for j in range(self.n):
                pert=x.copy();pert[j]+=eps;self.apply(pert);features=self.features(coords(self.mesh)*self.units,cs)
                jac[:,j]=np.einsum('ij,ij->i',features-base,normals)/eps
            self.apply(x);rhs=self.profile['clearance_m']-gaps
            step=np.linalg.solve(jac.T@jac+np.eye(self.n)*.0005,jac.T@rhs-.0002*(x-preferred))
            for j in range(0,self.n,3):
                size=np.linalg.norm(step[j:j+3])
                if size>math.radians(3):step[j:j+3]*=math.radians(3)/size
            previous=float(np.sum(np.maximum(rhs,0)**2));accepted=False
            for factor in (1,.5,.25,.1):
                candidate=self.bounded(x+factor*step)
                self.apply(candidate);nc=coords(self.mesh)*self.units;change=np.einsum('ij,ij->i',self.features(nc,cs)-base,normals)
                score=float(np.sum(np.maximum(rhs-change,0)**2))
                if score<previous-1e-12:x=candidate;accepted=True;break
            history.append({'iteration':it,'crossings':total,'constraints':len(cs),'accepted':accepted})
            if not accepted:break
        self.apply(x);final=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=False,cap=2000)
        remaining=sum(r['triangle_crossings']+r.get('contained_samples',0) for r in final['pairs'] if r['classification']=='ordinary_collision')
        return x,{'status':'SURFACE_SAMPLED_PASS' if not remaining else 'UNRESOLVED',
                  'remaining_crossings':remaining,'max_control_delta_deg':float(max(np.linalg.norm(x[j:j+3]) for j in range(0,self.n,3))*180/math.pi),'history':history}
