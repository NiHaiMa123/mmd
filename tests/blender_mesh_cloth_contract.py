"""Reject an unanchored cloth island before constructing a simulation."""
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.mesh_cloth import configure
me=bpy.data.meshes.new('TwoFabricIslands');me.from_pydata([(0,0,1),(1,0,1),(1,1,1),(0,1,1),(2,0,1),(3,0,1),(3,1,1),(2,1,1)],[],[(0,1,2,3),(4,5,6,7)])
obj=bpy.data.objects.new('Fabric',me);bpy.context.scene.collection.objects.link(obj);pin=obj.vertex_groups.new(name='Pins');pin.add([0,1],1.,'REPLACE')
bpy.ops.mesh.primitive_cube_add(size=1);body=bpy.context.object
count=len(bpy.data.objects)
try:configure(obj,'Pins',[body])
except ValueError as exc:assert 'island' in str(exc)
else:raise AssertionError('Unpinned lower skirt accepted')
assert len(bpy.data.objects)==count and not obj.modifiers
pin.add([4,5],1.,'REPLACE');sim,report=configure(obj,'Pins',[body],first=1,last=450)
assert sim.type=='CLOTH' and sim.settings.vertex_group_mass=='Pins'
assert sim.point_cache.frame_end==450 and report['island_pins']==[{'vertices':4,'fully_pinned':2}]*2
assert sim.collision_settings.use_self_collision
assert len(sim.collision_settings.collection.objects)==1
print('MESH_CLOTH_CONTRACT_OK: unpinned-island fail-fast, pins, collisions, frame interval')
