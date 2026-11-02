import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.joint_surface import JointSurfaceProjector
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);rows=[]
for f in (220,240,260,361,450):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();solver=JointSurfaceProjector(mesh,arm,p,parts);offset,result=solver.solve(iterations=35);result['frame']=f;rows.append(result);print('JOINT_SURFACE_PROBE',json.dumps(result),flush=True)
(out/'local_joint_surface_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
