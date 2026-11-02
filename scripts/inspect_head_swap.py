"""Read-only inventory of both heads before changing the dressed target."""
import sys,json,argparse
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--target',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.target,load_ui=False,use_scripts=False)
profile=read_json(a.profile);original=list(bpy.data.objects)

def inventory(objects):
 arm=next(o for o in objects if o.type=='ARMATURE');root=ie.mmd_root(arm)
 result={'armature':arm.name,'root':root.name,'meshes':[],'bones':[],'morphs':[]}
 for bone in arm.data.bones:
  if bone.head_local.z>1.1 or bone.name in ('首','頭','両目','目.L','目.R'):
   mb=arm.pose.bones[bone.name].mmd_bone
   result['bones'].append({'name':bone.name,'name_j':mb.name_j,'head':list(bone.head_local),'tail':list(bone.tail_local),'parent':bone.parent.name if bone.parent else None,'additional':{'rotation':mb.has_additional_rotation,'translation':mb.has_additional_location,'bone':mb.additional_transform_bone,'influence':mb.additional_transform_influence}})
 for obj in ie.model_meshes(objects):
  if obj.get('external_shoe'):continue
  names={g.index:g.name for g in obj.vertex_groups};rows=[]
  for index,material in enumerate(obj.data.materials):
   faces=[f for f in obj.data.polygons if f.material_index==index]
   ids=sorted({i for f in faces for i in f.vertices})
   if not ids:continue
   points=[obj.matrix_world@obj.data.vertices[i].co for i in ids]
   dominant=Counter(max(((g.weight,names[g.group]) for g in obj.data.vertices[i].groups if not names[g.group].startswith('mmd_')),default=(0,'NONE'))[1] for i in ids)
   rows.append({'slot':index,'name':material.name,'name_j':material.mmd_material.name_j,'faces':len(faces),'vertices':len(ids),'bounds':[[min(p[k] for p in points),max(p[k] for p in points)] for k in range(3)],'dominant_bones':dict(dominant.most_common(12))})
  result['meshes'].append({'name':obj.name,'vertices':len(obj.data.vertices),'faces':len(obj.data.polygons),'materials':rows,'shape_keys':list(obj.data.shape_keys.key_blocks.keys()) if obj.data.shape_keys else []})
 for kind in ('vertex_morphs','bone_morphs','material_morphs','uv_morphs','group_morphs'):
  result['morphs'].append({'kind':kind,'count':len(getattr(root.mmd_root,kind)),'names':[m.name for m in getattr(root.mmd_root,kind)]})
 result['physics']={'rigids':[{'name':o.name,'bone':o.mmd_rigid.bone,'type':o.mmd_rigid.type} for o in objects if getattr(o,'mmd_type','')=='RIGID_BODY'],'joints':sum(getattr(o,'mmd_type','')=='JOINT' for o in objects)}
 return result

report={'target_file':a.target,'source_file':profile['source']['path'],'target':inventory(original)}
source=ie.import_pmx(profile['source']['path']);report['source']=inventory(source)
write_json(out/'inventory.json',report)
original=[o for o in original if o.type in {'MESH','ARMATURE'}]
for label in ('target','source'):
 print('HEAD_INVENTORY',label,json.dumps({'meshes':[{k:v for k,v in row.items() if k!='shape_keys'} for row in report[label]['meshes']],'head_bones':[b for b in report[label]['bones'] if b['name'] in ('首','頭','両目','目.L','目.R')]},ensure_ascii=False),flush=True)
for obj in bpy.context.scene.objects:obj.hide_render=True
scene=bpy.context.scene;render._setup_render(scene,1000,1000);render._setup_lights(scene)
data=bpy.data.cameras.new('HeadInspectCamera');data.type='ORTHO';data.ortho_scale=.40
camera=bpy.data.objects.new('HeadInspectCamera',data);scene.collection.objects.link(camera);scene.camera=camera
for label,objects in [('target',original),('source',source)]:
 for obj in ie.model_meshes(objects):
  if not obj.get('external_shoe'):obj.hide_render=False
 arm=next(o for o in objects if o.type=='ARMATURE');head=arm.data.bones['頭'];center=head.head_local.lerp(head.tail_local,.45)
 for name,direction in [('front',(0,-1,.01)),('side',(1,0,.01)),('oblique',(.7,-1,.05)),('back',(0,1,.01))]:
  camera.location=center+Vector(direction).normalized()*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
  scene.render.filepath=str(out/f'{label}_{name}.png');bpy.ops.render.render(write_still=True)
 for obj in ie.model_meshes(objects):obj.hide_render=True
print('HEAD_INSPECTION_COMPLETE',out,flush=True)
