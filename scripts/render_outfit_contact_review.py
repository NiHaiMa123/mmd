"""Native 1080p clothed contact inspection from controlled viewpoints."""
import argparse,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--blend',required=True);p.add_argument('--output',required=True);p.add_argument('--frame',type=int,default=325);p.add_argument('--views',nargs='+',default=['front','front_left','side_left','back','side_right','front_right']);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.blend).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];scene.frame_set(a.frame);bpy.context.view_layer.update();scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='TEXTURE';scene.display.shading.show_cavity=True;scene.display.shading.show_shadows=True;scene.display.shading.background_type='WORLD';scene.world.color=(.6,.6,.6);data=bpy.data.cameras.new('OutfitContactReview');data.type='ORTHO';data.ortho_scale=.85;cam=bpy.data.objects.new('OutfitContactReview',data);scene.collection.objects.link(cam);scene.camera=cam;upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3();center=arm.matrix_world@upper.head+Vector((0,0,.09));views={'front':(0,-2,.15),'front_left':(1.3,-2,.1),'side_left':(2,0,.1),'back':(0,2,.15),'side_right':(-2,0,.1),'front_right':(-1.3,-2,.1),'low_front':(0,-2,-.45)}
for view in a.views:
    cam.location=center+axes@Vector(views[view]);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{a.frame}_{view}.png');bpy.ops.render.render(write_still=True)
print('OUTFIT_CONTACT_VIEWS_RENDERED',str(out),flush=True)
