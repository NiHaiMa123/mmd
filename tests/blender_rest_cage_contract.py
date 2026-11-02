"""Two unrelated rigid skin regions touch in a pose, then separate."""
import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.skin_collision_cage import build_skin_cage,audit_skin_cage
from animation_contact_tools.surface import coords
from animation_contact_tools.anatomical_colliders import split_rest_cage
bpy.ops.wm.read_factory_settings(use_empty=True)
data=bpy.data.armatures.new('RestCageContract');arm=bpy.data.objects.new('GenericRig',data);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,x in [('core',0.),('moving',.5)]:
 b=data.edit_bones.new(name);b.head=(x,0,0);b.tail=(x,0,.1)
bpy.ops.object.mode_set(mode='OBJECT');objects=[]
for name,x in [('core',0.),('moving',.5)]:
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3,radius=.14,location=(x,0,0));o=bpy.context.object;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);g=o.vertex_groups.new(name=name);g.add(list(range(len(o.data.vertices))),1.,'REPLACE');objects.append(o)
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();mesh=bpy.context.object;mod=mesh.modifiers.new('Plain LBS','ARMATURE');mod.object=arm;attr=mesh.data.attributes.new('SurfaceClass','INT','FACE');attr.data.foreach_set('value',np.ones(len(mesh.data.polygons),dtype=np.int32));profile={'units_to_m':1.,'surface_attribute':'SurfaceClass','body_classes':[1],'head_classes':[]}
arm.pose.bones['moving'].location.x=-.3;bpy.context.view_layer.update();source=coords(mesh).copy()
posed,_=build_skin_cage(mesh,arm,profile,voxel_size=.012,binding_pose='CURRENT')
rest,metadata=build_skin_cage(mesh,arm,profile,voxel_size=.012,binding_pose='REST')
assert arm.data.pose_position=='POSE';np.testing.assert_array_equal(coords(mesh),source)
arm.pose.bones['moving'].location.x=0.;bpy.context.view_layer.update()
old=audit_skin_cage(mesh,posed,profile);new=audit_skin_cage(mesh,rest,profile)
oldpeak=max(old['samples'][k]['unsigned_distance_peak_m'] for k in ('face_centres','edge_midpoints'));newpeak=max(new['samples'][k]['unsigned_distance_peak_m'] for k in ('face_centres','edge_midpoints'))
assert oldpeak>.04,(oldpeak,newpeak)
assert newpeak<.015,(oldpeak,newpeak)
parts={'source_faces':{'torso':[p.index for p in mesh.data.polygons if p.center.y<0], 'arm.R':[p.index for p in mesh.data.polygons if p.center.y>=0]}}
closed,split=split_rest_cage(mesh,arm,rest,profile,parts)
assert len(closed)==2 and all(p['nonmanifold_edges']==0 for p in split['parts'])
assert sum(p['joint_cap_faces'] for p in split['parts'])>=4
assert arm.data.pose_position=='POSE'
for obj in closed:
 assert all(abs(sum(g.weight for g in v.groups)-1)<1e-6 for v in obj.data.vertices)
try:build_skin_cage(mesh,arm,dict(profile,units_to_m=.01),binding_pose='REST')
except ValueError:pass
else:raise AssertionError('Unsupported unit conversion was accepted')
assert arm.data.pose_position=='POSE'
result={'status':'REST_CAGE_AVOIDS_POSED_CONTACT_MEMBRANE_PASS','mmd_required':False,'original_pose_restored':True,'old_face_interior_peak_m':oldpeak,'rest_face_interior_peak_m':newpeak,'binding_pose':metadata['binding_pose'],'closed_anatomical_parts':split['parts'],'restored_pose_after_error':True}
out=ROOT/'outputs/rest_cage_contract';out.mkdir(parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');print('REST_CAGE_CONTRACT',json.dumps(result),flush=True)
