"""Experimental fixed-length hair-bone projection against actual body surfaces.

This does not simulate cloth, preserve all strand strain, or certify CCD.
It deliberately keeps attachment bones and the complete body pose fixed.
"""
from collections import defaultdict
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,intersect_ray_tri
from .surface import audit_frame,coords
from .projector import exp_quat

class HairProjector:
    def __init__(self,mesh,arm,profile,parts,limit_degrees=30,max_active=12):
        self.mesh,self.arm,self.profile,self.parts=mesh,arm,profile,parts
        self.targets=set(profile.get('hair_collision_targets',('head','torso','arm.L','arm.R','hand.L','hand.R','leg.L','leg.R')))
        self.contact_cache={}
        self.units=profile.get('units_to_m',1.);self.limit=np.radians(limit_degrees);self.max_active=max_active
        anchors=set(profile.get('root_hair_anchor_bones',[]));body_names={n for role,names in profile['bone_roles'].items() if role!='head' for n in names}
        groups={g.index:g.name for g in mesh.vertex_groups};weighted=set();self.influences=[]
        for v in mesh.data.vertices:
            weights={groups[g.group]:g.weight for g in v.groups if g.weight>.001 and groups[g.group] in arm.pose.bones}
            self.influences.append(weights)
        for i in parts['ids'].get('hair_mobile',[]):weighted.update(self.influences[i])
        eligible=set()
        for n in weighted:
            b=arm.data.bones.get(n)
            while b and b.name not in anchors and b.name not in body_names:
                eligible.add(b.name);b=b.parent
        self.bones=[b for b in arm.pose.bones if b.name in eligible]
        self.names={b.name:i for i,b in enumerate(self.bones)};self.n=len(self.bones)*3
        if not self.bones:raise ValueError('No movable hair bones; provide explicit attachment anchors and a weighted hair rig')
        if any(b.rotation_mode!='QUATERNION' for b in self.bones):raise ValueError('Hair adapter requires quaternion control channels')
        # Inherited influence estimates only select controls. Actual Jacobians
        # below still use Blender's evaluated skin and its existing constraints.
        self.affected=[]
        for weights in self.influences:
            inherited=defaultdict(float)
            for n,w in weights.items():
                b=arm.data.bones[n]
                while b:
                    if b.name in self.names:inherited[self.names[b.name]]+=w
                    b=b.parent
            self.affected.append(inherited)

    def capture(self):self.base=[b.rotation_quaternion.copy() for b in self.bones]

    def bounded(self,x):
        x=np.asarray(x,dtype=float).copy()
        for j in range(0,self.n,3):
            size=np.linalg.norm(x[j:j+3])
            if size>self.limit:x[j:j+3]*=self.limit/size
        return x

    def apply(self,x):
        for i,b in enumerate(self.bones):b.rotation_quaternion=self.base[i]@exp_quat(x[i*3:i*3+3])
        self.arm.update_tag();bpy.context.view_layer.update()

    def constraints(self,audit,co):
        trees={};result=[];witness_results=[];basis=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
        def tree(r):
            if r not in trees:trees[r]=BVHTree.FromPolygons(co.tolist(),self.parts['faces'][r],all_triangles=True)
            return trees[r]
        for row in audit['pairs']:
            a,b=row['pair']
            if not a.startswith('hair') or b not in self.targets:continue
            moving,target_vertices=set(row['moving_vertices']),set(row['target_vertices'])
            if self.profile.get('hair_keep_contacts',False):
                saved=self.contact_cache.setdefault((a,b),set());saved.update(moving);moving=saved
            elif not row['triangle_crossings']:continue
            for hair_tri,body_tri in row.get('witness_pairs',[]):
                ha=[Vector(co[i]) for i in hair_tri];bo=[Vector(co[i]) for i in body_tri];hits=[]
                for first,second in ((ha,bo),(bo,ha)):
                    for k in range(3):
                        start,end=first[k],first[(k+1)%3];direction=end-start
                        if direction.length_squared<1e-14:continue
                        hit=intersect_ray_tri(*second,direction,start,True)
                        if hit is not None and 0<=(hit-start).dot(direction)/direction.length_squared<=1:hits.append(hit)
                if not hits or not any(self.affected[i] for i in hair_tri):continue
                point=sum(hits,Vector())/len(hits);normal=(bo[1]-bo[0]).cross(bo[2]-bo[0])
                if normal.length<1e-10:continue
                normal.normalize();hm=list(barycentric_transform(point,*ha,*basis));bw=list(barycentric_transform(point,*bo,*basis));witness_results.append((hair_tri,hm,body_tri,bw,np.array(normal),0.))
            for reverse,indices in [(False,moving),(True,target_vertices)]:
                target=a if reverse else b
                for i in indices:
                    q,n,fi,d=tree(target).find_nearest(Vector(co[i]))
                    if q is None or d>.06:continue
                    signed=(Vector(co[i])-q).dot(n)
                    if not reverse and i not in row['moving_vertices'] and (d>.012 or signed<-.004):continue
                    if signed>=self.profile['clearance_m'] or (d>1e-6 and abs(signed)/d<.5):continue
                    tri=self.parts['faces'][target][fi];weights=barycentric_transform(q,*[Vector(co[k]) for k in tri],*basis)
                    if reverse:im,wm,it,wt,normal=list(tri),list(weights),[i],[1.],np.array(-n)
                    else:im,wm,it,wt,normal=[i],[1.],list(tri),list(weights),np.array(n)
                    if not any(self.affected[j] for j in im):continue
                    result.append((im,wm,it,wt,normal,float(signed)))
        result.sort(key=lambda c:c[-1]);limit=self.profile.get('hair_contact_constraint_limit',300)
        if witness_results:
            budget=min(len(witness_results),limit//2);ids=np.linspace(0,len(witness_results)-1,budget,dtype=int);return [witness_results[i] for i in ids]+result[:limit-budget]
        return result[:limit]

    @staticmethod
    def features(co,cs):return np.array([np.asarray(wm)@co[im]-np.asarray(wt)@co[it] for im,wm,it,wt,n,d in cs]).reshape(-1,3)

    def solve(self,initial=None,iterations=30):
        x=self.bounded(np.zeros(self.n) if initial is None else initial);history=[];self.apply(x)
        for iteration in range(iterations):
            audit=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=True,cap=1500);co=coords(self.mesh)*self.units;cs=self.constraints(audit,co)
            total=sum(r['triangle_crossings'] for r in audit['pairs'] if r['pair'][0].startswith('hair'))
            if not cs:break
            importance=defaultdict(float)
            for im,wm,it,wt,n,d in cs:
                for i in im:
                    for j,w in self.affected[i].items():importance[j]+=w*(self.profile['clearance_m']-d)
            selected=sorted(importance,key=importance.get,reverse=True)[:self.max_active];dofs=[j*3+k for j in selected for k in range(3)]
            normals=np.array([c[-2] for c in cs]);rhs=self.profile['clearance_m']-np.array([c[-1] for c in cs]);base=self.features(co,cs);jac=np.zeros((len(cs),len(dofs)))
            for j,dof in enumerate(dofs):
                pert=x.copy();pert[dof]+=.001;self.apply(pert);jac[:,j]=np.einsum('ij,ij->i',self.features(coords(self.mesh)*self.units,cs)-base,normals)/.001
            self.apply(x);step=np.linalg.solve(jac.T@jac+np.eye(len(dofs))*.0003,jac.T@rhs-.0001*x[dofs])
            for j in range(0,len(step),3):
                size=np.linalg.norm(step[j:j+3])
                if size>np.radians(3):step[j:j+3]*=np.radians(3)/size
            accepted=False;previous=float(np.sum(np.maximum(rhs,0)**2))
            for factor in (1,.5,.25,.1):
                proposal=x.copy();proposal[dofs]+=step*factor;proposal=self.bounded(proposal);self.apply(proposal)
                change=np.einsum('ij,ij->i',self.features(coords(self.mesh)*self.units,cs)-base,normals)
                if float(np.sum(np.maximum(rhs-change,0)**2))<previous-1e-12:x=proposal;accepted=True;break
            history.append({'iteration':iteration,'crossings':total,'constraints':len(cs),'active_bones':len(selected),'accepted':accepted})
            if not accepted:break
        self.apply(x);final=audit_frame(self.mesh,self.arm,self.profile,self.parts,hair=True,cap=2000)
        rows=[r for r in final['pairs'] if r['pair'][0].startswith('hair')]
        return x,{'status':'HAIR_SURFACE_ONLY_PASS_REQUIRES_STRAIN_CHECK' if not sum(r['triangle_crossings'] for r in rows) else 'HAIR_UNRESOLVED',
          'remaining_crossings':sum(r['triangle_crossings'] for r in rows),'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in rows],
          'max_delta_degrees':float(max(np.linalg.norm(x[j:j+3]) for j in range(0,self.n,3))*180/np.pi),'history':history,'fixed_attachment_bones':self.profile.get('root_hair_anchor_bones',[])}
