"""Unrelated smooth-weighted hair rig verifies the analytic accelerator."""
import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.surface import regions
from animation_contact_tools.strain_hair import StrainHairProjector
from animation_contact_tools.hair_skin_jacobian import HairSkinJacobian
bpy.ops.wm.read_factory_settings(use_empty=True);ad=bpy.data.armatures.new('GenericHairRigData');arm=bpy.data.objects.new('GenericHairRig',ad);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for n,h,t,parent in [('trunk',(0,0,.5),(0,0,1.4),None),('skull',(0,0,1.45),(0,0,1.7),'trunk'),('guide_a',(.17,0,1.6),(.17,.05,1.3),'skull'),('guide_b',(.17,.05,1.3),(.17,.1,1.),'guide_a')]:
 b=ad.edit_bones.new(n);b.head=h;b.tail=t
 if parent:b.parent=ad.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
objects=[]
for center,radius,bone,cls in [((0,0,.8),.2,'trunk',1),((0,0,1.6),.15,'skull',2)]:
 bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=radius,location=center);o=bpy.context.object;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);vg=o.vertex_groups.new(name=bone);vg.add(list(range(len(o.data.vertices))),1,'REPLACE');attr=o.data.attributes.new('SurfaceClass','INT','FACE')
 for v in attr.data:v.value=cls
 objects.append(o)
vertices=[(.14+.03*col,.012*row,1.6-.09*row) for row in range(9) for col in range(3)];faces=[]
for row in range(8):
 for col in range(2):
  a=row*3+col;faces.extend([(a,a+1,a+4),(a,a+4,a+3)])
data=bpy.data.meshes.new('HairRibbon');data.from_pydata(vertices,[],faces);hair=bpy.data.objects.new('HairRibbon',data);bpy.context.scene.collection.objects.link(hair);attr=data.attributes.new('SurfaceClass','INT','FACE')
for v in attr.data:v.value=3
groups={n:hair.vertex_groups.new(name=n) for n in ('skull','guide_a','guide_b')}
for row in range(9):
 weights={'skull':1.} if row==0 else {'skull':.85,'guide_a':.15} if row==1 else {'guide_a':1.} if row<4 else {'guide_a':max(0,1-(row-3)/4),'guide_b':min(1,(row-3)/4)}
 for name,w in weights.items():
  if w:groups[name].add([row*3+i for i in range(3)],w,'REPLACE')
objects.append(hair);bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();mesh=bpy.context.object;mesh.name='GenericHairSurface';mod=mesh.modifiers.new('Skin','ARMATURE');mod.object=arm
p={'schema':1,'units_to_m':1.,'surface_attribute':'SurfaceClass','body_classes':[1],'head_classes':[2],'hair_classes':[3],'exclude_classes':[0,4,5],'bone_roles':{'torso':['trunk'],'head':['skull','guide_a','guide_b']},'root_hair_anchor_bones':['skull'],'pairs':[],'protected_pairs':[],'protected_windows':[],'clearance_m':.003};rows=[];rest=np.array([v.co[:] for v in mesh.data.vertices])
for scale,units in [(1.,1.),(100.,.01)]:
 for b in arm.pose.bones:b.rotation_quaternion=(1,0,0,0)
 mesh.scale=(scale,scale,scale);arm.scale=(scale,scale,scale);bpy.context.view_layer.update();profile=dict(p,units_to_m=units);parts=regions(mesh,arm,profile);solver=StrainHairProjector(mesh,arm,profile,parts);solver.capture();x=np.array([.08,.04,.03,-.02,.06,-.04]);solver.apply(x);analytic=HairSkinJacobian(solver);ids=sorted(set(parts['ids']['hair_root']+parts['ids']['hair_mobile']));r=analytic.verify(x,ids,list(range(6)));r.update(world_scale=scale,units_to_m=units);rows.append(r)
assert np.array_equal(rest,np.array([v.co[:] for v in mesh.data.vertices]));out=ROOT/'outputs/portable_hair_jacobian';out.mkdir(parents=True,exist_ok=True);report={'status':'GENERIC_NONZERO_ROTATION_AND_CENTIMETRE_JACOBIAN_PASS','samples':rows,'rest_mesh_unchanged':True,'mmd_tools_required':False};(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('HAIR_JACOBIAN_CONTRACT',json.dumps(report),flush=True)
