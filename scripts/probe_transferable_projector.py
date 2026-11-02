import sys,json,argparse,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame
from animation_contact_tools.projector import FrameProjector
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--profile',required=True);p.add_argument('--out',required=True);p.add_argument('--frames',nargs='+',type=int,default=[1,100,230,240,250,360,440]);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()),load_ui=False,use_scripts=False)
profile=json.loads(Path(a.profile).read_text('utf8'));profile['protected_windows']=[{'start':256,'end':321,'intent':'defer clasp/crossed hand interaction'}]
mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile)
controls=profile.get('control_chains',[['左腕','左ひじ','左手首'],['右腕','右ひじ','右手首']]);profile['control_chains']=controls
solver=FrameProjector(mesh,arm,profile,parts,controls);rows=[];out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
for f in a.frames:
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();solver.capture();before=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
 start=time.monotonic();x,report=solver.solve(iterations=28)
 row={'frame':f,'before_crossings':before['ordinary_crossings'],'offsets':x.tolist(),**report,'seconds':time.monotonic()-start};rows.append(row)
 print('PROJECTOR_PROBE',json.dumps(row),flush=True)
(out/'frame_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');(out/'rig_profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
