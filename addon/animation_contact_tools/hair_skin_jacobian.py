"""Analytic LBS hair Jacobian, gated by an actual Blender forward-skin check.

Only plain hierarchical deform bones are supported. This is an accelerator for
the same mesh-contact objective, not a substitute collision representation.
"""
import numpy as np
import bpy
from .surface import coords

def right_jacobian(v):
    angle=float(np.linalg.norm(v));x,y,z=v;skew=np.array([[0,-z,y],[z,0,-x],[-y,x,0]],dtype=float)
    if angle<1e-7:return np.eye(3)-.5*skew+skew@skew/6
    return np.eye(3)-(1-np.cos(angle))/angle**2*skew+(angle-np.sin(angle))/angle**3*(skew@skew)

class HairSkinJacobian:
    def __init__(self,solver):
        self.solver=solver;self.mesh=solver.mesh;self.arm=solver.arm;self.units=solver.units
        mods=[m for m in self.mesh.modifiers if m.type=='ARMATURE' and m.show_viewport]
        if len(mods)!=1 or mods[0].object!=self.arm or mods[0].use_deform_preserve_volume or mods[0].vertex_group or mods[0].use_bone_envelopes:raise ValueError('Analytic accelerator needs one unmasked linear-blend armature modifier')
        if any(len(b.constraints) or b.bone.inherit_scale!='FULL' for b in solver.bones):raise ValueError('Constrained/nonstandard hair bones require the evaluated finite-difference backend')
        mod=mods[0];mod.show_viewport=False;bpy.context.view_layer.update();rest_world=coords(self.mesh)/1.;mod.show_viewport=True;bpy.context.view_layer.update()
        world=np.asarray(self.arm.matrix_world);inverse=np.linalg.inv(world);self.rest=np.c_[rest_world,np.ones(len(rest_world))]@inverse.T
        names={g.index:g.name for g in self.mesh.vertex_groups if g.name in self.arm.data.bones and self.arm.data.bones[g.name].use_deform};all_names=sorted(set(names.values()));self.deform_names=all_names;deform_index={n:i for i,n in enumerate(all_names)};self.rest_inverse=np.array([np.linalg.inv(np.array(self.arm.data.bones[n].matrix_local)) for n in all_names])
        vertices=[];deforms=[];weights=[];control_records=[]
        for vertex in self.mesh.data.vertices:
            groups=[(names[g.group],g.weight) for g in vertex.groups if g.group in names and g.weight>0];total=sum(w for n,w in groups)
            for name,w in groups:
                normalized=w/total;idx=len(vertices);vertices.append(vertex.index);deforms.append(deform_index[name]);weights.append(normalized);bone=self.arm.data.bones[name]
                while bone:
                    if bone.name in solver.names:control_records.append((idx,solver.names[bone.name]))
                    bone=bone.parent
        self.vertex=np.asarray(vertices,dtype=int);self.deform=np.asarray(deforms,dtype=int);self.weights=np.asarray(weights,dtype=float);records=np.array(control_records,dtype=int);self.record=records[:,0];self.control=records[:,1]
        predicted=self.forward();actual=coords(self.mesh)*self.units;hairids=sorted(set(solver.parts['ids']['hair_root']+solver.parts['ids']['hair_mobile']));self.forward_error=float(np.linalg.norm(predicted[hairids]-actual[hairids],axis=1).max())
        if self.forward_error>1e-5:raise ValueError(f'Analytic LBS differs from evaluated hair by {self.forward_error:.8g} m')

    def transformed_points(self):
        pose=np.array([np.array(self.arm.pose.bones[n].matrix) for n in self.deform_names]);matrix=np.asarray(self.arm.matrix_world)[None,:,:]@pose@self.rest_inverse
        return np.einsum('nij,nj->ni',matrix[self.deform],self.rest[self.vertex])[:,:3]*self.units

    def forward(self):
        result=np.zeros((len(self.mesh.data.vertices),3));np.add.at(result,self.vertex,self.transformed_points()*self.weights[:,None]);return result

    def vertices(self,ids,x):
        ids=np.asarray(ids,dtype=int);lookup=np.full(len(self.mesh.data.vertices),-1,dtype=int);lookup[ids]=np.arange(len(ids));records=self.record[lookup[self.vertex[self.record]]>=0];controls=self.control[lookup[self.vertex[self.record]]>=0];source_vertex=self.vertex[records];local=lookup[source_vertex];points=self.transformed_points()[records]
        world=np.asarray(self.arm.matrix_world);axes=[];origins=[]
        for i,bone in enumerate(self.solver.bones):
            orientation=np.array(bone.matrix.to_quaternion().to_matrix());axes.append(orientation@right_jacobian(x[3*i:3*i+3]));origins.append(np.array(bone.head))
        axes=np.asarray(axes);origins=np.asarray(origins);arm_points=(points/self.units-world[:3,3])@np.linalg.inv(world[:3,:3]).T;cross=np.cross(axes[controls].transpose(0,2,1),arm_points[:,None,:]-origins[controls,None,:]);cross=(cross@world[:3,:3].T)*self.units;cross*=self.weights[records,None,None]
        result=np.zeros((len(ids),len(self.solver.bones),3,3));np.add.at(result,(local,controls),cross);return result.reshape(len(ids),self.solver.n,3),lookup

    def verify(self,x,vertex_ids,controls):
        base=coords(self.mesh)*self.units;jac,lookup=self.vertices(vertex_ids,x);errors=[];epsilon=.001
        for dof in controls:
            pert=x.copy();pert[dof]+=epsilon;self.solver.apply(pert);actual=(coords(self.mesh)[vertex_ids]*self.units-base[vertex_ids])/epsilon;expected=jac[:,dof,:];errors.append(float(np.linalg.norm(actual-expected,axis=1).max()))
        self.solver.apply(x);maximum=max(errors,default=0.)
        if maximum>.0015:raise ValueError(f'Analytic derivative differs from Blender by {maximum:.8g} m/rad')
        return {'forward_error_m':self.forward_error,'max_derivative_error_m_per_rad':maximum,'checked_dofs':list(controls)}
