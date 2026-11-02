"""Cached pre-skin body positions with actual Blender pose matrices.

This is an optional LBS accelerator. Callers must compare its output against
the native evaluated mesh at representative changed poses before hiding the
mesh during an optimization. Constrained bones are read from Blender, not
reimplemented. DQ, envelopes, masks and multiple armatures are unsupported.
"""
import numpy as np
import bpy


class LinearSkinPlayback:
    def __init__(self,mesh,arm,vertex_ids):
        self.mesh=mesh;self.arm=arm;self.ids=np.asarray(vertex_ids,dtype=int);self.active=False
        modifiers=[m for m in mesh.modifiers if m.type=='ARMATURE' and m.show_viewport]
        if len(modifiers)!=1 or modifiers[0].object!=arm:raise ValueError('One active matching armature modifier required')
        self.modifier=modifiers[0]
        if self.modifier.use_deform_preserve_volume or self.modifier.use_bone_envelopes or self.modifier.vertex_group or not self.modifier.use_vertex_groups:raise ValueError('Unmasked vertex-group linear blend skinning required')
        if any(getattr(c,'target',None)==mesh for b in arm.pose.bones for c in b.constraints):raise ValueError('Mesh-dependent bone constraints require native evaluation')
        self.old_hidden=mesh.hide_viewport;self.old_enabled=self.modifier.show_viewport
        groups={g.index:g.name for g in mesh.vertex_groups if g.name in arm.data.bones and arm.data.bones[g.name].use_deform};self.names=sorted(set(groups.values()));lookup={n:i for i,n in enumerate(self.names)};vertices=[];bones=[];weights=[];weighted=np.zeros(len(self.ids),dtype=bool)
        for local,index in enumerate(self.ids):
            entries=[(groups[g.group],g.weight) for g in mesh.data.vertices[int(index)].groups if g.group in groups and g.weight>0];total=sum(w for n,w in entries)
            if total:
                weighted[local]=True
                for name,w in entries:vertices.append(local);bones.append(lookup[name]);weights.append(w/total)
        self.vertices=np.asarray(vertices,dtype=int);self.bones=np.asarray(bones,dtype=int);used=np.unique(self.bones);self.names=[self.names[i] for i in used];self.bones=np.searchsorted(used,self.bones);self.weights=np.asarray(weights);self.weighted=weighted;self.inverse_rest=np.array([np.linalg.inv(np.array(arm.data.bones[n].matrix_local)) for n in self.names])

    def capture_rest(self,world_positions):
        inverse=np.linalg.inv(np.array(self.arm.matrix_world));p=np.asarray(world_positions)[self.ids];return np.c_[p,np.ones(len(p))]@inverse.T

    def forward(self,rest):
        if not len(self.names):return (rest@np.array(self.arm.matrix_world).T)[:,:3]
        world=np.array(self.arm.matrix_world);pose=np.array([np.array(self.arm.pose.bones[n].matrix) for n in self.names]);matrices=world[None,:,:]@pose@self.inverse_rest;points=np.einsum('nij,nj->ni',matrices[self.bones],rest[self.vertices])[:,:3];out=np.zeros((len(self.ids),3));np.add.at(out,self.vertices,points*self.weights[:,None]);out[~self.weighted]=(rest[~self.weighted]@world.T)[:,:3];return out

    def hide(self):
        self.modifier.show_viewport=self.old_enabled;self.mesh.hide_viewport=True;self.active=True;bpy.context.view_layer.update()

    def restore(self):
        self.mesh.hide_viewport=self.old_hidden;self.modifier.show_viewport=self.old_enabled;self.active=False;bpy.context.view_layer.update()
