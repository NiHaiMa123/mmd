"""Neutral multi-angle actual-skin renders to inspect corrected poses."""
import sys,json,argparse,math
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands
p=argparse.ArgumentParser();p.add_argument('--fit',default='trial');p.add_argument('--frames',nargs='+',type=int,default=[47,280,310,407]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/contact_motion'/a.fit;bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];corrected=arm.animation_data.action
if 'シニカルナイトプラン_bone' not in bpy.data.actions:
    with bpy.data.libraries.load(str(ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend'),link=False) as (src,dst):dst.actions=['シニカルナイトプラン_bone']
original=bpy.data.actions['シニカルナイトプラン_bone'];regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth'])
for obj in bpy.data.objects:
    obj.hide_render=obj not in [body]+regions['extra_objects']
    if obj.type=='MESH':obj.color=(.38,.48,.59,1)
for obj in regions['extra_objects']:obj.hide_set(False);obj.hide_render=False;obj.color=(.9,.55,.16,1)
data=bpy.data.cameras.new('ContactReview');data.type='ORTHO';data.ortho_scale=1.35;cam=bpy.data.objects.new('ContactReview',data);scene.collection.objects.link(cam);scene.camera=cam
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.7,.7,.7)
out=folder/'review';out.mkdir(exist_ok=True)
for f in a.frames:
    for label,action in [('before',original),('after',corrected)]:
        arm.animation_data.action=action;scene.frame_set(f);bpy.context.view_layer.update();center=arm.matrix_world@arm.pose.bones['上半身3'].head+Vector((0,0,.0))
        for view,offset in [('front',(0,-3,.15)),('side',(3,-.4,.15)),('back',(0,3,.15))]:
            cam.location=center+Vector(offset);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{f}_{label}_{view}.png');bpy.ops.render.render(write_still=True)
print('CONTACT_POSES_READY',str(out),flush=True)
