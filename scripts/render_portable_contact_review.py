"""Matched-view upper-body diagnostic only, not the production material render."""
import sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;mesh=bpy.data.objects['东雪莲x达妮娅_素体'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];ad=arm.animation_data;original=bpy.data.actions['シニカルナイトプラン_bone']
for o in scene.objects:o.hide_render=o!=mesh
mesh.hide_render=False;mesh.color=(.53,.64,.78,1)
data=bpy.data.cameras.new('UpperBodyDiagnostic');data.type='ORTHO';data.ortho_scale=1.15;cam=bpy.data.objects.new('UpperBodyDiagnostic',data);scene.collection.objects.link(cam);scene.camera=cam
target=Vector((.6091568,-1.7871176,1.22));cam.location=target+Vector((0,-3,.025));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=960;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.fps=30;scene.render.film_transparent=False;scene.world.color=(.12,.12,.12)
shade=scene.display.shading;shade.light='STUDIO';shade.color_type='OBJECT';shade.show_cavity=True;shade.show_shadows=True;shade.background_type='WORLD'
for label in ('before','after'):
 ad.use_nla=label=='after';ad.action=None if label=='after' else original;out=root/'review_video_frames'/label;out.mkdir(parents=True,exist_ok=True)
 for frame in range(1,451):
  targetfile=out/f'f{frame:04}.png'
  if targetfile.exists():continue
  scene.frame_set(frame);bpy.context.view_layer.update();scene.render.filepath=str(targetfile);bpy.ops.render.render(write_still=True)
 print('CONTACT_REVIEW_RENDERED',label,flush=True)
