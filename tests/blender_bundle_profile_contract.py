"""Explicit bundle selection on an independent English armature."""
import json,sys,copy
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.hair_bundle_profile import resolve_bundle
bpy.ops.wm.read_factory_settings(use_empty=True)
data=bpy.data.meshes.new('Hair');data.from_pydata([(0,0,0),(1,0,0),(0,1,0),(2,0,0),(3,0,0),(2,1,0)],[],[(0,1,2),(3,4,5)])
mesh=bpy.data.objects.new('Hair',data);bpy.context.scene.collection.objects.link(mesh)
ad=bpy.data.armatures.new('Rig');arm=bpy.data.objects.new('Rig',ad);bpy.context.scene.collection.objects.link(arm);bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,parent,z in [('Head',None,0),('Root','Head',1),('Tip','Root',2),('Other','Head',3)]:
 b=ad.edit_bones.new(name);b.head=(0,0,z);b.tail=(0,0,z+.5)
 if parent:b.parent=ad.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
parts={'faces':{'hair_root':[(0,1,2)],'hair_mobile':[(3,4,5)]},'source_faces':{'hair_root':[0],'hair_mobile':[1]},'ids':{},'samples':{},'closed':{}}
config={'schema':1,'vertex_ids':[0,1,2],'source_vertex_count':6,'guide_bones':['Root','Tip'],'anchor_bone':'Head'}
r=resolve_bundle(mesh,arm,parts,config);assert r['ids'].tolist()==[0,1,2] and r['parts']['faces']['hair_mobile']==[(0,1,2)]
assert parts['faces']['hair_mobile']==[(3,4,5)]
r=resolve_bundle(mesh,arm,parts,dict(config,root_vertex_ids=[0,2]));assert r['root_pin_mask'].tolist()==[True,False,True]
rejections=0
for changes in [{'vertex_ids':[0,1]},{'vertex_ids':[0,0,1]},{'source_vertex_count':7},{'guide_bones':['Root','Other']},{'anchor_bone':'Missing'},{'root_vertex_ids':[4]},{'root_vertex_ids':[0,0]}]:
 try:resolve_bundle(mesh,arm,parts,dict(config,**changes))
 except ValueError:rejections+=1
 else:raise AssertionError(changes)
out=ROOT/'outputs/bundle_profile_contract';out.mkdir(parents=True,exist_ok=True);report={'status':'EXPLICIT_BUNDLE_PROFILE_PASS','invalid_configurations_rejected':rejections,'source_parts_unchanged':True};(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('BUNDLE_PROFILE_CONTRACT',json.dumps(report),flush=True)
