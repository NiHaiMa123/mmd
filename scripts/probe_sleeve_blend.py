"""Compare sleeve mixing against the actual cached cloth at problem poses."""
import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();out=ROOT/'outputs/sleeve_13s/blend_probe';out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/chest_hd/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;proxy=bpy.data.objects['ClothSimulationSurface'];ref=bpy.data.objects['ClothKinematicReference'];target=bpy.data.objects['ClothShapePreservingTarget'];attr=ref.data.attributes['OutfitClothMotion'];original=[d.value for d in attr.data];ids={v.index for v in proxy.data.vertices if any(proxy.vertex_groups[g.group].name in ('腕.L','腕.R') and g.weight>.5 for g in v.groups)};render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('SleeveMixProbe');data.type='ORTHO';data.ortho_scale=1.45;cam=bpy.data.objects.new('SleeveMixProbe',data);scene.collection.objects.link(cam);scene.camera=cam;arm=bpy.data.objects['达妮娅_arm']
for strength in (.90,1.0):
 for i in ids:attr.data[i].value=strength
 ref.update_tag(refresh={'DATA'})
 for frame in (407,437,447):
  scene.frame_set(frame);center=arm.matrix_world@arm.pose.bones['上半身2'].head+Vector((0,0,-.1))
  for view,d in [('front',(0,-1,0)),('back',(0,1,0))]:
   cam.location=center+Vector(d)*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'mix_{strength:.2f}_{frame}_{view}.png');bpy.ops.render.render(write_still=True)
print('SLEEVE_BLEND_PROBE_COMPLETE',flush=True)
