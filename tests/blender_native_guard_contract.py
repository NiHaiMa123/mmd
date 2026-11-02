"""Regression: authored normals survive extraction; guarded regions validate."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.native_guard import add_skin_guard
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
mesh=bpy.data.meshes.new('Authored');mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)]);mesh.materials.append(bpy.data.materials.new('TestMaterial'));mesh.polygons[0].use_smooth=True
normal=Vector((0,.2,.98)).normalized();mesh.normals_split_custom_set([normal]*3);obj=bpy.data.objects.new('Authored',mesh);bpy.context.scene.collection.objects.link(obj);obj.vertex_groups.new(name='Bone').add([0,1,2],1.,'REPLACE');obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Pose');key.data[1].co.z=.1
copy,ids=engine('garment')._copy_mesh_subset(obj,[0],'Copied');assert copy.data.has_custom_normals
error=max((a.vector-b.vector).length for a,b in zip(mesh.corner_normals,copy.data.corner_normals))
# Blender packs custom normals; re-encoding introduces about 5e-5 here.
assert error<1e-4,(error,[tuple(a.vector) for a in mesh.corner_normals],[tuple(a.vector) for a in copy.data.corner_normals])
assert abs(copy.data.shape_keys.key_blocks['Pose'].data[1].co.z-.1)<1e-7
bpy.ops.mesh.primitive_cube_add(size=2);body=bpy.context.object;body.name='TestSkin';mat=bpy.data.materials.new('Body');mat.mmd_material.name_j='Body';body.data.materials.append(mat)
bpy.ops.mesh.primitive_cube_add(size=1.96);cloth=bpy.context.object;cloth.name='TestClothing';cloth.vertex_groups.new(name='Region').add(list(range(8)),1.,'REPLACE')
before=len(bpy.data.objects)
try:add_skin_guard(body,cloth,'Missing')
except ValueError:pass
else:raise AssertionError('Missing region was accepted')
assert len(bpy.data.objects)==before and not cloth.modifiers
result=add_skin_guard(body,cloth,'Region');assert result['portable_to_pmx'] is False
evaluated=cloth.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh();assert all(max(abs(c) for c in v.co)>.999 for v in me.vertices);evaluated.to_mesh_clear()
print('NATIVE_GUARD_CONTRACT_OK: normals, morphs, fail-fast region, exterior correction')
