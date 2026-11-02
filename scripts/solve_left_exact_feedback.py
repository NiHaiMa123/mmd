import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.attachment_feedback import solve_attachment_feedback
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';directory=root/'left_arm_feedback_refined';source=json.loads((directory/'source.json').read_text('utf8'))['source'];profile=json.loads((directory/'profile.json').read_text('utf8'));profile['clearance_m']=.003;envelope=json.loads((directory/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');envelope['attachment_points']=initial['coordinates'][initial['pinned']].tolist();engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];out=root/'left_exact_feedback_v2';out.mkdir(exist_ok=True)
for name,data in [('profile.json',profile),('envelope.json',envelope),('source.json',{'source':source})]:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
r=solve_attachment_feedback(mesh,arm,profile,regions(mesh,arm,profile),envelope,out,centres=(240,242,244,246,248),width=2.,limit_degrees=20.,iterations=40,sample_step=.5);print('LEFT_EXACT_FEEDBACK',json.dumps({k:v for k,v in r.items() if k not in ('quarter_samples','history','coefficients')}),flush=True)
