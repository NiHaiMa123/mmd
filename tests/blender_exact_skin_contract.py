"""Closing a missing face preserves source vertices and follows actual skin."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
from animation_contact_tools.closed_collider_field import ClosedColliderField
from animation_contact_tools.surface import coords
from animation_contact_tools.hair_position_cache import bind_position_cache
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add(size=.2);mesh=bpy.context.object;verts=[tuple(v.co) for v in mesh.data.vertices];faces=[tuple(p.vertices) for p in list(mesh.data.polygons)[:-1]];data=bpy.data.meshes.new('OpenSkin');data.from_pydata(verts,[],faces);mesh.data=data
ad=bpy.data.armatures.new('SkinRig');arm=bpy.data.objects.new('SkinRig',ad);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bone=ad.edit_bones.new('core');bone.head=(0,0,0);bone.tail=(0,0,.3);bpy.ops.object.mode_set(mode='OBJECT');group=mesh.vertex_groups.new(name='core');group.add(list(range(8)),1.,'REPLACE');mod=mesh.modifiers.new('LBS','ARMATURE');mod.object=arm;attr=data.attributes.new('SurfaceClass','INT','FACE');attr.data.foreach_set('value',np.ones(len(data.polygons),dtype=np.int32));profile={'units_to_m':1.,'body_classes':[1],'head_classes':[],'surface_attribute':'SurfaceClass'}
arm.pose.bones['core'].location.x=.25;bpy.context.view_layer.update();original=coords(mesh).copy();ids,closed,metadata=build_exact_skin_topology(mesh,arm,profile);assert arm.data.pose_position=='POSE';np.testing.assert_array_equal(coords(mesh),original);assert metadata['cap_faces']==1
field=ClosedColliderField(coords(mesh)[ids],closed);d,_=field(np.array([[.25,0,0],[.5,0,0]]));assert (d<0).tolist()==[True,False],d
tree=field.tree;coverage=max(tree.find_nearest(Vector(v))[3] for v in original);assert coverage<1e-6

# A posed, measured skin cache must not corrupt REST seam topology. Restore both
# enabled and disabled measured modifiers on success and on closure failure.
cache_out=ROOT/'outputs/exact_skin_contract';cache_out.mkdir(parents=True,exist_ok=True)
positions=np.array([original+np.array([0.,.1,0.]),original+np.array([0.,.1,0.])])
bind_position_cache(mesh,np.arange(8),positions,cache_out/'fixture.pc2',first=1,namespace='RestFixture')
cached=coords(mesh).copy();modifier=mesh.modifiers[-1]
ids2,faces2,meta2=build_exact_skin_topology(mesh,arm,profile)
assert modifier.show_viewport and arm.data.pose_position=='POSE'
np.testing.assert_array_equal(coords(mesh),cached)
np.testing.assert_array_equal(ids2,ids);assert faces2==closed
modifier.show_viewport=False;bpy.context.view_layer.update()
build_exact_skin_topology(mesh,arm,profile);assert not modifier.show_viewport
modifier.show_viewport=True;bpy.context.view_layer.update()
broken=dict(profile,surface_attribute='MissingSurfaceClass')
try:build_exact_skin_topology(mesh,arm,broken)
except (ValueError,KeyError,RuntimeError):pass
else:raise AssertionError('Missing skin classes should fail')
assert modifier.show_viewport and arm.data.pose_position=='POSE'
out=ROOT/'outputs/exact_skin_contract';out.mkdir(parents=True,exist_ok=True);r={'status':'SOURCE_SKIN_COVERAGE_BOUNDARY_CAP_AND_POSE_RESTORE_PASS','metadata':metadata,'source_vertex_coverage_error_m':coverage};(out/'report.json').write_text(json.dumps(r,indent=2),encoding='utf8');print('EXACT_SKIN_CONTRACT',json.dumps(r),flush=True)
