import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,DEFAULT_PAIRS,coords
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p)
rows=[]
for f in (1,180,240,361,420):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
 for mode in ('POSE','REST'):
  arm.data.pose_position=mode;bpy.context.view_layer.update();a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000);co=coords(mesh)
  hits=[]
  for row in a['pairs']:
   if not row['triangle_crossings']:continue
   samples=[]
   for ex in row['examples'][:2]:
    v=ex['a_triangle'][0];w=[(mesh.vertex_groups[g.group].name,g.weight) for g in mesh.data.vertices[v].groups if g.weight>.001];samples.append({**ex,'a_first_vertex_weights':w})
   hits.append({'pair':row['pair'],'count':row['triangle_crossings'],'examples':samples})
  rows.append({'frame':f,'mode':mode,'hits':hits})
  print('JOINT_CONTACT',f,mode,[(r['pair'],r['count']) for r in hits],flush=True)
arm.data.pose_position='POSE';bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
(out/'diagnosis.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
scene=bpy.context.scene
for o in scene.objects:o.hide_render=o!=mesh
mesh.hide_render=False;mesh.color=(.53,.64,.78,1)
data=bpy.data.cameras.new('JointReview');data.type='ORTHO';cam=bpy.data.objects.new('JointReview',data);scene.collection.objects.link(cam);scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1080;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.18,.18,.18);shade=scene.display.shading;shade.light='STUDIO';shade.color_type='OBJECT';shade.show_cavity=True;shade.show_shadows=True;shade.background_type='WORLD'
for f,pair in [(1,('hand.R','arm.R')),(180,('leg.L','torso')),(420,('leg.R','torso'))]:
 scene.frame_set(f);bpy.context.view_layer.update();a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000);co=coords(mesh);row=next(r for r in a['pairs'] if tuple(r['pair'])==pair)
 if not row['examples']:continue
 target=Vector(co[row['examples'][0]['a_triangle']].mean(0));data.ortho_scale=.28
 for label,offset in [('front',(0,-2,0)),('side',(2,0,0)),('rear',(0,2,0))]:
  cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'f{f:04}_{pair[0]}_{label}.png');bpy.ops.render.render(write_still=True)
