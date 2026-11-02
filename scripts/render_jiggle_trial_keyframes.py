"""Normal complete-character views of each already-baked full-head trial."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(a.root);engine('import_export').ensure_mmd_tools();started=time.monotonic()
for name in ['C_shorter_root','B_smaller_radius','A_ellipsoids_only']:
 folder=root/name;receipt=json.loads((folder/'bake_report.json').read_text('utf8'));bpy.ops.wm.open_mainfile(filepath=receipt['blend'],load_ui=False,use_scripts=False);s=bpy.context.scene;assert s.render.fps==30;assert s.camera and not s.camera.animation_data and not s.camera.constraints;assert not s.rigidbody_world or not s.rigidbody_world.enabled
 prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for device in prefs.devices:device.use=device.type=='OPTIX'
 s.cycles.device='GPU';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.use_persistent_data=True;s.render.use_sequencer=False;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_depth='8';s.render.image_settings.color_mode='RGB';camera=np.array(s.camera.matrix_world);out=folder/'keyframes';out.mkdir(exist_ok=True)
 for f in [1,331,356,376]:
  s.frame_set(f);bpy.context.view_layer.update();assert np.abs(np.array(s.camera.matrix_world)-camera).max()<1e-9;s.render.filepath=str(out/f'f{f:04d}.png');bpy.ops.render.render(write_still=True);print('JIGGLE_TRIAL_KEYFRAME',name,f,time.monotonic()-started,flush=True)
(root/'keyframes_complete.json').write_text(json.dumps(dict(status='ALL3TRIALS_4NORMAL_KEYFRAMES_EACH_COMPLETE',new_simulation=False,elapsed_s=time.monotonic()-started)),'utf8')
