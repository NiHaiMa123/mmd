"""Inspect whether blending old/new skin weights removes waist seam artifacts."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);ie=engine('import_export');ie.ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/chest_hd';template=json.loads((folder/'torso_template.json').read_text(encoding='utf-8'));ids=[int(i) for i in template['vertices']]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/structured_v2/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);cloth=bpy.data.objects['Cloth'];valid=set(bpy.data.objects['达妮娅_arm'].data.bones.keys());names={g.index:g.name for g in cloth.vertex_groups};old={i:{names[g.group]:g.weight for g in cloth.data.vertices[i].groups if names[g.group] in valid} for i in ids}
bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;cloth=bpy.data.objects['Cloth'];arm=bpy.data.objects['达妮娅_arm'];names={g.index:g.name for g in cloth.vertex_groups};changed=0
for i in ids:
 z=cloth.data.vertices[i].co.z;b=min(np.clip((z-1.08)/.065,0,1),np.clip((1.373-z)/.043,0,1));b=b*b*(3-2*b)
 if b>.999999:continue
 new={names[g.group]:g.weight for g in cloth.data.vertices[i].groups if names[g.group] in valid};weights={name:old[i].get(name,0)*(1-b)+new.get(name,0)*b for name in old[i].keys()|new.keys()};top=sorted(weights.items(),key=lambda p:-p[1])[:4];total=sum(v for _,v in top)
 for g in list(cloth.data.vertices[i].groups):
  if names[g.group] in valid:cloth.vertex_groups[g.group].remove([i])
 for name,weight in top:
  group=cloth.vertex_groups.get(name) or cloth.vertex_groups.new(name=name);group.add([i],weight/total,'REPLACE')
 changed+=1
cloth.update_tag(refresh={'DATA'})
if a.apply:
 scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),compress=True)
report={'weights_blended_vertices':changed,'geometry_and_morphs_unchanged':True,'applied':a.apply};(folder/('weight_boundary_applied.json' if a.apply else 'weight_boundary_probe.json')).write_text(json.dumps(report),encoding='utf-8')
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('BoundaryInspect');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('BoundaryInspect',data);scene.collection.objects.link(cam);scene.camera=cam
for name,frame in [('end_450',496),('arms_up',376)]:
 scene.frame_set(frame);target=arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.055,.015));cam.location=target+Vector((0,-2,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(folder/('boundary_'+name+'.png'));bpy.ops.render.render(write_still=True)
print('WEIGHT_BOUNDARY',json.dumps(report),flush=True)
