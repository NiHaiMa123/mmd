"""Native 1080p comparison of the critical motion interval; sleeves omitted."""
import sys,argparse
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands
p=argparse.ArgumentParser();p.add_argument('--fit',default='body_contact_v1');p.add_argument('--start',type=int,default=287);p.add_argument('--end',type=int,default=376);a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);folder=ROOT/'outputs/cynical_cloth15/contact_motion'/a.fit
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];corrected=arm.animation_data.action;original=bpy.data.actions['シニカルナイトプラン_bone'];regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,cloth)
for obj in bpy.data.objects:obj.hide_render=True
body.hide_render=False;body.color=(.36,.43,.55,1)
for obj in regions['extra_objects']:obj.hide_render=False;obj.color=(.75,.45,.17,1);obj.hide_set(False)
names={g.index:g.name for g in cloth.vertex_groups if g.name in arm.pose.bones};dom=[max(((g.weight,names[g.group]) for g in v.groups if g.group in names),default=(0,''))[1] for v in cloth.data.vertices];faces=[f.index for f in cloth.data.polygons if all(dom[i].startswith(('上半身','下半身','胸','首','おっぱい','乳')) and cloth.data.vertices[i].co.z>.88 for i in f.vertices)]
torso,_=engine('garment')._copy_mesh_subset(cloth,faces,'ContactReviewTorsoClothing');torso.modifiers.new('Torso skinning','ARMATURE').object=arm;torso.hide_render=False;torso.color=(.30,.20,.55,1)
data=bpy.data.cameras.new('ContactComparisonCamera');data.type='ORTHO';data.ortho_scale=.95;cam=bpy.data.objects.new('ContactComparisonCamera',data);scene.collection.objects.link(cam);scene.camera=cam
textdata=bpy.data.curves.new('ContactComparisonCaption','FONT');textdata.size=.028;text=bpy.data.objects.new('ContactComparisonCaption',textdata);scene.collection.objects.link(text);text.parent=cam;text.location=(-.39,.40,-1);text.color=(.03,.03,.04,1);text.hide_render=False
scene.render.engine='BLENDER_WORKBENCH';scene.render.resolution_x=960;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.fps=30;scene.display.shading.light='STUDIO';scene.display.shading.color_type='OBJECT';scene.display.shading.show_cavity=True;scene.display.shading.show_shadows=True;scene.display.shading.background_type='WORLD';scene.world.color=(.8,.8,.8);scene.render.film_transparent=False
for label,action in [('before',original),('after',corrected)]:
    arm.animation_data.action=action;dest=folder/'comparison_frames'/label;dest.mkdir(parents=True,exist_ok=True)
    for f in range(a.start,a.end+1):
        scene.frame_set(f);bpy.context.view_layer.update();center=arm.matrix_world@arm.pose.bones['上半身3'].head+Vector((0,0,.04));cam.location=center+Vector((0,-3,.15));cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();textdata.body=('Original motion' if label=='before' else 'Contact motion prototype')+f'  {(f-47)/30:.2f}s\nSleeves hidden for body inspection';scene.render.filepath=str(dest/f'{f:04d}.png');bpy.ops.render.render(write_still=True)
print('CONTACT_COMPARISON_RENDERED',str(folder),flush=True)
