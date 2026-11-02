"""Stable sleeve offsets stay rigid while all barycentric weights are bounded."""
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.stable_sleeve_cloth import bind_clamped_frames
mesh=bpy.data.meshes.new('Rest');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);target=bpy.data.objects.new('Target',mesh);bpy.context.scene.collection.objects.link(target)
original=[Vector((.2,.2,.12)),Vector((1.2,.2,-.1)),Vector((3.,-2.,.03))];me=bpy.data.meshes.new('Carrier');me.from_pydata(original,[],[(0,1,2)]);carrier=bpy.data.objects.new('Carrier',me);bpy.context.scene.collection.objects.link(carrier);bind_clamped_frames(carrier,target,mesh,[0],{0,1,2})
for i in range(3):
 weights=[me.attributes['SleeveStableW'+str(k)].data[i].value for k in range(3)];assert all(0<=w<=1 for w in weights);assert abs(sum(weights)-1)<1e-6
matrix=Matrix.Translation((2,-1,3))@Matrix.Rotation(.7,4,'Y');target.matrix_world=matrix;bpy.context.view_layer.update();ev=carrier.evaluated_get(bpy.context.evaluated_depsgraph_get());result=ev.to_mesh();error=max((v.co-matrix@p).length for v,p in zip(result.vertices,original));ev.to_mesh_clear();assert error<1e-5,error
# Large triangle deformation cannot amplify a negative outside-triangle weight.
target.matrix_world=Matrix.Identity(4);mesh.vertices[2].co=(0,.001,0);mesh.update();target.update_tag(refresh={'DATA'});bpy.context.view_layer.update();ev=carrier.evaluated_get(bpy.context.evaluated_depsgraph_get());result=ev.to_mesh();assert all(v.co.length<4 for v in result.vertices);ev.to_mesh_clear()
print('STABLE_SLEEVE_TRANSFER_CONTRACT_OK',error)
