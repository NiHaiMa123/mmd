"""Case adapter for the generic local joint volume corrective."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.local_volume_skin import bake_local_volume_skin
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--probe',required=True);p.add_argument('--out',required=True);p.add_argument('--blend',type=float,default=.75);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise ValueError('Use a new corrective output directory')
r=json.loads((src/'report.json').read_text('utf8'));probe=Path(a.probe);check=json.loads((probe/'probe.json').read_text('utf8'))
if not any(x['blend']==a.blend and x['failed_samples']==0 for x in check['summary']):raise ValueError('Choose a blend with zero probe failures')
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['candidate'],load_ui=False,use_scripts=False);profile=r['rig_profile'];mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];mask=np.load(probe/'wrist_mask.npz');first,last=r['frames']
result=bake_local_volume_skin(mesh,arm,mask['ids'],mask['weights'],profile['control_chains'][0][2],out/'wrist_volume.pc2',first=first,last=last,blend=a.blend)
candidate=out/'Body_Spline_And_LocalWristVolume_Candidate.blend';bpy.context.scene.frame_set(245);bpy.ops.wm.save_as_mainfile(filepath=str(candidate));r.update(status='LOCAL_WRIST_VOLUME_REQUIRES_INDEPENDENT_VALIDATION',candidate=str(candidate),accepted=False,parent_run=str(src),joint_volume=result,failed_samples=None,samples=[])
(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('LOCAL_VOLUME_BAKED',json.dumps(result),flush=True)
