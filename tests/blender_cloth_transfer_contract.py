"""Absolute carrier transfer must preserve rigid transforms and normal offset."""
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.structured_cloth import _bind_carrier
mesh=bpy.data.meshes.new('Rest');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);target=bpy.data.objects.new('Target',mesh);bpy.context.scene.collection.objects.link(target)
original=[Vector((.2,.2,.12)),Vector((.7,.1,-.1)),Vector((1.2,.2,.03))];me=bpy.data.meshes.new('Carrier');me.from_pydata(original,[],[(0,1,2)]);carrier=bpy.data.objects.new('Carrier',me);bpy.context.scene.collection.objects.link(carrier);_bind_carrier(carrier,target,mesh)
matrix=Matrix.Translation((2,-1,3))@Matrix.Rotation(.7,4,'Y');target.matrix_world=matrix;bpy.context.view_layer.update();ev=carrier.evaluated_get(bpy.context.evaluated_depsgraph_get());result=ev.to_mesh();error=max((v.co-matrix@p).length for v,p in zip(result.vertices,original));ev.to_mesh_clear();assert error<1e-5,error
assert not any(m.type=='ARMATURE' for m in carrier.modifiers)
print('CLOTH_TRANSFER_CONTRACT_OK: rigid transform, signed offset, outside-triangle binding',error)
