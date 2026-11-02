"""Audit collision-cage membranes over requested motion frames."""
import argparse,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.skin_collision_cage import audit_skin_cage
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--frames',default='1,200,230,235,236,240,300,440');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run=Path(a.run)
profile=json.loads((ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track/rig_profile.json').read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(run/'NativeSingleBundle_Live_NotAccepted.blend'),load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];cage=bpy.data.objects['ContactSkinCage'];rows=[]
for f in [int(x) for x in a.frames.split(',')]:
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();r=audit_skin_cage(mesh,cage,profile);rows.append(r);print('CAGE_FACE_AUDIT',f,{k:round(v['unsigned_distance_peak_m']*1000,2) for k,v in r['samples'].items()},flush=True)
(run/'cage_surface_audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
