"""Compare original outfit chest geometry to the transferred result."""
import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();source=json.loads((ROOT/'outputs/keqing_head/proportions_v2/head_swap_report.json').read_text(encoding='utf-8'))['source'];ie.clear_scene();objects=ie.import_pmx(source);arm=next(o for o in objects if o.type=='ARMATURE');render=engine('extraction');scene=bpy.context.scene;render._setup_render(scene,1080,1080);render._setup_lights(scene);scene.view_settings.view_transform='AgX';model=set(ie.model_meshes(objects))
for o in objects:o.hide_render=o not in model
data=bpy.data.cameras.new('SourceChest');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('SourceChest',data);scene.collection.objects.link(cam);scene.camera=cam;center=arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.04,.015));out=ROOT/'outputs/chest_repair/source';out.mkdir(parents=True,exist_ok=True)
for name,d in [('front',(0,-1,0)),('side',(1,-1,0))]:
    cam.location=center+Vector(d).normalized()*2;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('ORIGINAL_CHEST_RENDERED',source,flush=True)
