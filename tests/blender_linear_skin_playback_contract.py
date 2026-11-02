"""Native skin agreement with object transforms, morphs and constrained bones."""
import json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.linear_skin_playback import LinearSkinPlayback
from animation_contact_tools.surface import coords
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.mesh.primitive_cube_add(size=.2,location=(.1,.2,.3));mesh=bpy.context.object;mesh.name='MorphSkin';mesh.shape_key_add(name='Basis');key=mesh.shape_key_add(name='Morph');key.data[0].co.z+=.03;key.value=.65
data=bpy.data.armatures.new('RigData');arm=bpy.data.objects.new('Rig',data);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT');upper=data.edit_bones.new('Upper');upper.head=(0,0,0);upper.tail=(0,0,.3);twist=data.edit_bones.new('Twist');twist.head=(0,0,.3);twist.tail=(0,0,.6);twist.parent=upper;bpy.ops.object.mode_set(mode='OBJECT');arm.location=(.3,-.2,.1);arm.scale=(1.3,1.3,1.3)
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
driver=bpy.data.objects.new('RotationTarget',None);bpy.context.scene.collection.objects.link(driver);constraint=arm.pose.bones['Twist'].constraints.new('COPY_ROTATION');constraint.target=driver
mesh.vertex_groups.new(name='Upper').add(list(range(7)),.4,'REPLACE');mesh.vertex_groups.new(name='Twist').add(list(range(7)),.6,'REPLACE');modifier=mesh.modifiers.new('Linear skin','ARMATURE');modifier.object=arm;bpy.context.view_layer.update();helper=LinearSkinPlayback(mesh,arm,np.arange(8));modifier.show_viewport=False;bpy.context.view_layer.update();rest=helper.capture_rest(coords(mesh));modifier.show_viewport=True;bpy.context.view_layer.update();maximum=0.
for angle in (0.,.2,-.35):
 helper.hide();arm.pose.bones['Upper'].rotation_quaternion=Quaternion((0,1,0),angle);driver.rotation_euler=(angle,.1,-angle);arm.update_tag();bpy.context.view_layer.update();predicted=helper.forward(rest);helper.restore();actual=coords(mesh);maximum=max(maximum,float(np.max(np.linalg.norm(actual-predicted,axis=1))))
 assert maximum<1e-6,maximum
assert mesh.hide_viewport is False and modifier.show_viewport is True
modifier.use_deform_preserve_volume=True
try:LinearSkinPlayback(mesh,arm,np.arange(8))
except ValueError:pass
else:raise AssertionError('DQ was silently treated as LBS')
result=dict(status='NATIVE_LBS_MORPH_OBJECT_TRANSFORM_CONSTRAINT_AND_UNWEIGHTED_PASS',maximum_forward_error_m=maximum)
(ROOT/'outputs/linear_skin_playback_contract.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result),flush=True)
