"""An unrelated, English-named rig exercises the public profile API."""
import sys,json
from pathlib import Path
import bpy,bmesh,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools import register,unregister
from animation_contact_tools.surface import regions,audit_frame
from animation_contact_tools.projector import FrameProjector
bpy.ops.wm.read_factory_settings(use_empty=True)
arm_data=bpy.data.armatures.new('DemoSkeleton');arm=bpy.data.objects.new('GenericDemoRig',arm_data);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
defs=[('origin',(0,0,0),(0,0,.2),None),('core',(0,0,.2),(0,0,.6),'origin'),('skull',(0,0,.8),(0,0,1),'core'),
 ('reachA',(-.7,0,1),(-.45,-.04,1),'origin'),('bendA',(-.45,-.04,1),(-.22,-.08,1),'reachA'),('palmA',(-.22,-.08,1),(-.15,-.08,1),'bendA')]
for name,h,t,parent in defs:
 b=arm_data.edit_bones.new(name);b.head=h;b.tail=t
 if parent:b.parent=arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
objs=[]
for name,center,radius,bone,cls in [('CoreSurface',(0,.12,.43),.18,'core',1),('HeadSurface',(0,0,1),.18,'skull',2),('PalmSurface',(-.20,-.08,1),.07,'palmA',1)]:
 bpy.ops.object.select_all(action='DESELECT');bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=radius,location=center);o=bpy.context.object;o.name=name
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);vg=o.vertex_groups.new(name=bone);vg.add(list(range(len(o.data.vertices))),1,'REPLACE')
 attr=o.data.attributes.new('SurfaceClass','INT','FACE')
 for d in attr.data:d.value=cls
 objs.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();mesh=bpy.context.object;mesh.name='GenericDemoSurface';mod=mesh.modifiers.new('Deform','ARMATURE');mod.object=arm
profile={'schema':1,'mesh':mesh.name,'armature':arm.name,'units_to_m':1.,'bone_roles':{'torso':['core'],'head':['skull'],'arm.L':['reachA','bendA'],'hand.L':['palmA']},
 'surface_attribute':'SurfaceClass','body_classes':[1],'head_classes':[2],'hair_classes':[3],'exclude_classes':[0,4,5],
 'pairs':[['hand.L','head']],'protected_pairs':[],'protected_windows':[],'root_hair_anchor_bones':['skull'],'clearance_m':.003,
 'control_chains':[['reachA','bendA','palmA']],'protected_bones':['core','skull','origin']}
parts=regions(mesh,arm,profile);assert not parts['missing_body_mapping'];before=audit_frame(mesh,arm,profile,parts,hair=False)
assert before['ordinary_crossings']>0
out=ROOT/'outputs/portable_contact_contract';out.mkdir(parents=True,exist_ok=True)
for frame in (1,8):
 for bone in arm.pose.bones:bone.keyframe_insert('rotation_quaternion',frame=frame)
bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=8
bpy.ops.wm.save_as_mainfile(filepath=str(out/'GenericContactInput.blend'),compress=True)
protected={n:np.array(arm.pose.bones[n].matrix) for n in profile['protected_bones']};rest=np.array([v.co[:] for v in mesh.data.vertices])
solver=FrameProjector(mesh,arm,profile,parts,profile['control_chains'],limit_degrees=25);solver.capture();x,result=solver.solve(iterations=35)
assert result['remaining_crossings']==0,result
assert all(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))<1e-7 for n,m in protected.items())
assert np.array_equal(rest,np.array([v.co[:] for v in mesh.data.vertices]))
bounded_seed=solver.bounded(np.ones(solver.n)*10)
assert max(np.linalg.norm(bounded_seed[i:i+3]) for i in range(0,solver.n,3))<=solver.limit+1e-9
# The same physical scene expressed in centimetres must still find and fix it.
solver.apply(np.zeros(solver.n));mesh.scale*=100;arm.scale*=100;mesh.update_tag();arm.update_tag();bpy.context.view_layer.update()
centimetre_profile=dict(profile,units_to_m=.01);cm_parts=regions(mesh,arm,centimetre_profile)
assert audit_frame(mesh,arm,centimetre_profile,cm_parts,hair=False)['ordinary_crossings']==before['ordinary_crossings']
cm_solver=FrameProjector(mesh,arm,centimetre_profile,cm_parts,profile['control_chains'],limit_degrees=25);cm_solver.capture();cm_x,cm_result=cm_solver.solve(iterations=35)
assert cm_result['remaining_crossings']==0,cm_result
mesh.scale/=100;arm.scale/=100;mesh.update_tag();arm.update_tag();bpy.context.view_layer.update()
# A fully enclosed palm has zero triangle crossings; it must still be detected.
solver.apply(np.zeros(solver.n));palm=mesh.vertex_groups['palmA'].index
for v in mesh.data.vertices:
 if any(g.group==palm and g.weight>.5 for g in v.groups):v.co.x+=.20;v.co.y+=.08
mesh.data.update();arm.update_tag();bpy.context.view_layer.update();parts2=regions(mesh,arm,profile);inside=audit_frame(mesh,arm,profile,parts2,hair=False)
assert inside['ordinary_crossings']==0,inside
assert inside['ordinary_contained_samples']>0,inside
# Imported surfaces can have reversed normals; containment uses ray parity.
bm=bmesh.new();bm.from_mesh(mesh.data);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(mesh.data);bm.free();mesh.data.update();bpy.context.view_layer.update()
reversed_inside=audit_frame(mesh,arm,profile,regions(mesh,arm,profile),hair=False)
assert reversed_inside['ordinary_contained_samples']>0,reversed_inside
register();assert hasattr(bpy.types.Scene,'animation_contact');unregister()
report={'status':'NON_MMD_RIG_PROFILE_AND_ADDON_REGISTRATION_PASS','mmd_tools_required':False,
 'before_crossings':before['ordinary_crossings'],'after_crossings':result['remaining_crossings'],
 'original_mesh_rest_positions_unchanged':True,'protected_bones_unchanged':True,
 'centimetre_scene_collision_and_solve_pass':True,'oversized_seed_is_bounded':True,
 'fully_contained_case_detected':inside['ordinary_contained_samples'],'bone_names':[x[0] for x in defs]}
report['reversed_normals_containment_detected']=reversed_inside['ordinary_contained_samples']
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');(out/'rig_profile.json').write_text(json.dumps(profile,indent=2),encoding='utf8');print('PORTABLE_CONTRACT_PASS',json.dumps(report),flush=True)
