import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.adaptive import refine_layer
engine('import_export').ensure_mmd_tools();out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/body_track'
bpy.ops.wm.open_mainfile(filepath=str(out/'BodyContact_Refined.blend'),load_ui=False,use_scripts=False)
p=json.loads((out/'rig_profile.json').read_text('utf8'));r=json.loads((out/'body_track_report.json').read_text('utf8'));arm=bpy.data.objects[p['armature']];mesh=bpy.data.objects[p['mesh']];parts=regions(mesh,arm,p)
result=refine_layer(mesh,arm,p,parts,bpy.data.actions[r['original_action']],bpy.data.actions[r['correction_action']],step=.25,passes=3,limit_degrees=25)
(out/'adaptive_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('ADAPTIVE_RESULT',result['status'],result['remaining'],flush=True)
bpy.context.scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'BodyContact_Adaptive.blend'),compress=True)
