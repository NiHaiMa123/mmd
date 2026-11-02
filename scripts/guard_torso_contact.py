"""Keep the lower corset clear of posed skin, without projecting the bust."""
import sys,json,argparse
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);engine('import_export').ensure_mmd_tools();folder=ROOT/'outputs/cynical_cloth15/chest_hd';bpy.ops.wm.open_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;cloth=bpy.data.objects['Cloth'];arm=bpy.data.objects['达妮娅_arm'];template=json.loads((folder/'torso_template.json').read_text(encoding='utf-8'));group=cloth.vertex_groups.get('TorsoWaistContact') or cloth.vertex_groups.new(name='TorsoWaistContact');count=0
for key in template['vertices']:
 i=int(key);z=cloth.data.vertices[i].co.z
 if not 1.075<z<1.155:continue
 strength=min(1.,max(0.,(1.155-z)/.025));group.add([i],strength,'REPLACE');count+=1
mod=cloth.modifiers.get('Waist outside posed skin') or cloth.modifiers.new('Waist outside posed skin','SHRINKWRAP');mod.target=bpy.data.objects['Outfit_SkinCollider'];mod.vertex_group=group.name;mod.wrap_method='NEAREST_SURFACEPOINT';mod.wrap_mode='OUTSIDE';mod.offset=.006
report={'selected_vertices':count,'offset_m':mod.offset,'only_lower_corset':True,'geometry_keys_unchanged':True,'applied':a.apply}
if a.apply:
 scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Cynical_Cloth_15s.blend'),compress=True)
(folder/('waist_contact_applied.json' if a.apply else 'waist_contact_probe.json')).write_text(json.dumps(report),encoding='utf-8')
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('WaistContactInspect');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('WaistContactInspect',data);scene.collection.objects.link(cam);scene.camera=cam
for name,frame in [('end_450',496),('arms_up',376)]:
 scene.frame_set(frame);target=arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.055,.015));cam.location=target+Vector((0,-2,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(folder/('waist_contact_'+name+'.png'));bpy.ops.render.render(write_still=True)
print('WAIST_CONTACT',json.dumps(report),flush=True)
