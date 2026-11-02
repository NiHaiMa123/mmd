import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);scene=bpy.context.scene
for o in scene.objects:o.hide_render=True
data=bpy.data.cameras.new('JointSurfaceReview');data.type='ORTHO';cam=bpy.data.objects.new('JointSurfaceReview',data);scene.collection.objects.link(cam);scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1080;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.world.color=(.18,.18,.18);shade=scene.display.shading;shade.light='STUDIO';shade.color_type='MATERIAL';shade.show_cavity=True;shade.show_shadows=True;shade.background_type='WORLD'
mats=[]
for n,c in [('body',(.53,.64,.78,1)),('moving',(.88,.21,.17,1)),('target',(.22,.73,.32,1))]:
 m=bpy.data.materials.new(n);m.diffuse_color=c;mats.append(m)
for f,pair in [(1,('hand.R','arm.R')),(240,('leg.L','torso')),(361,('leg.L','torso'))]:
 scene.frame_set(f);bpy.context.view_layer.update();a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000);co=coords(mesh);row=next(r for r in a['pairs'] if tuple(r['pair'])==pair)
 if not row['examples']:continue
 faces=[tri for r,fs in parts['faces'].items() if not r.startswith('hair') for tri in fs];dm=bpy.data.meshes.new('SurfaceCopy');dm.from_pydata(co.tolist(),[],faces);obj=bpy.data.objects.new('SurfaceCopy',dm);scene.collection.objects.link(obj)
 for m in mats:dm.materials.append(m)
 moving={tuple(ex['a_triangle']) for ex in row['examples']};target_tris={tuple(ex['b_triangle']) for ex in row['examples']}
 for face in dm.polygons:
  face.use_smooth=True
  if tuple(face.vertices) in moving:face.material_index=1
  elif tuple(face.vertices) in target_tris:face.material_index=2
 target=Vector(co[row['examples'][0]['a_triangle']].mean(0));data.ortho_scale=.30
 for label,offset in [('front',(0,-2,0)),('side',(2,0,0)),('rear',(0,2,0))]:
  cam.location=target+Vector(offset);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'surface_f{f:04}_{pair[0]}_{label}.png');bpy.ops.render.render(write_still=True)
 bpy.data.objects.remove(obj,do_unlink=True)
