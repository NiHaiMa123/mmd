import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal,clamp_reachable_goal
for target,expected in [([3.,0,0],1.49999),([.01,0,0],.50001),([1.,0,0],1.)]:
 projected,error=clamp_reachable_goal([0,0,0],(1.,.5),target)
 np.testing.assert_allclose(projected,[expected,0,0],atol=1e-8)
 assert abs(error-abs(target[0]-expected))<1e-8
try:clamp_reachable_goal([0,0,0],(1.,.5),[0,0,0])
except ValueError:pass
else:raise AssertionError('Singular goal accepted')
bpy.ops.wm.read_factory_settings(use_empty=True);data=bpy.data.armatures.new('GenericIK');arm=bpy.data.objects.new('GenericIK',data);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,head,tail,parent in [('upper',(0,0,0),(.2,0,.1),None),('bend',(.2,0,.1),(.25,.05,.3),'upper'),('palm',(.25,.05,.3),(.3,.05,.35),'bend')]:
 b=data.edit_bones.new(name);b.head=head;b.tail=tail
 if parent:b.parent=data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
rows=[]
for angle in (0.,.7):
 for b in arm.pose.bones:b.rotation_quaternion=(1,0,0,0)
 arm.matrix_world=Matrix.Translation((.3,-.4,.5))@Matrix.Rotation(angle,4,'Y');bpy.context.view_layer.update();before=(arm.matrix_world@arm.pose.bones['palm'].matrix).to_quaternion();target=arm.matrix_world@Vector((.26,-.03,.31));report=apply_two_bone_goal(arm,['upper','bend','palm'],target,1.,.1);orientation=before.rotation_difference((arm.matrix_world@arm.pose.bones['palm'].matrix).to_quaternion()).angle
 assert report['endpoint_error_m']<2e-6,report
 assert report['local_translation_error']==0 and report['local_scale_error']==0,report
 assert orientation<.001,orientation
 report.update(world_rotation=angle,wrist_orientation_error_rad=orientation);rows.append(report)
out=ROOT/'outputs/two_bone_goal_contract';out.mkdir(parents=True,exist_ok=True);result={'status':'ENGLISH_RIG_GOAL_WRIST_ORIENTATION_AND_NO_STRETCH_PASS','mmd_required':False,'samples':rows};(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('TWO_BONE_GOAL_CONTRACT',json.dumps(result),flush=True)
