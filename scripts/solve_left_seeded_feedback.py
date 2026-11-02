"""Use a discrete geometric route as a basin seed, not as accepted motion."""
import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions
from animation_contact_tools.attachment_feedback import solve_attachment_feedback
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal
from animation_contact_tools.arm_detour_planner import interpolate_waypoints
from animation_contact_tools.root_envelope_feedback import cubic_basis
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';directory=root/'left_arm_feedback_refined';source=json.loads((directory/'source.json').read_text('utf8'))['source'];profile=json.loads((directory/'profile.json').read_text('utf8'));profile['clearance_m']=.003;envelope=json.loads((directory/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');envelope['attachment_points']=initial['coordinates'][initial['pinned']].tolist();route=json.loads((directory/'planned_route.json').read_text('utf8'))['waypoints'];engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];out=root/'left_exact_seeded_feedback';out.mkdir(exist_ok=True)
centres=(240,242,244,246,248);basis=[];rotations=[];chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain]
for f in np.arange(236,252.001,.25):
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();old=[b.rotation_quaternion.copy() for b in bones];p=interpolate_waypoints(route,f);goal=np.array(arm.matrix_world@bones[2].head)+p[:3];apply_two_bone_goal(arm,chain,goal,1.,p[3]);basis.append(cubic_basis(f,centres,2.));rotations.append(np.concatenate([np.array((q.inverted()@b.rotation_quaternion).to_exponential_map()) for q,b in zip(old,bones)]))
coeff=np.linalg.lstsq(np.asarray(basis),np.asarray(rotations),rcond=None)[0];(out/'seed.json').write_text(json.dumps({'coefficients':coeff.tolist(),'route':str(directory/'planned_route.json'),'max_fit_error_rad':float(np.max(np.linalg.norm(np.array(basis)@coeff-rotations,axis=1)))},indent=2),encoding='utf8')
for name,data in [('profile.json',profile),('envelope.json',envelope),('source.json',{'source':source})]:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
r=solve_attachment_feedback(mesh,arm,profile,regions(mesh,arm,profile),envelope,out,centres=centres,width=2.,limit_degrees=85.,iterations=40,sample_step=.5,initial_coefficients=coeff);print('LEFT_SEEDED_FEEDBACK',json.dumps({k:v for k,v in r.items() if k not in ('quarter_samples','history','coefficients')}),flush=True)
