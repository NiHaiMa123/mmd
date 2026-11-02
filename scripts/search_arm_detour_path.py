import sys,json,time,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.root_envelope_feedback import capsule_features
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal,smooth_detour
parser=argparse.ArgumentParser();parser.add_argument('--direction',choices=['head','side','up','front','back','upback'],default='head');options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_arm_feedback_20261028'/('analytic_'+options.direction+'_detour');out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);chain=p['control_chains'][1];env=json.loads((base/'hair_arm_feedback_20261028/root_contact_diagnosis.json').read_text('utf8'));direction=next(r for r in json.loads((base/'hair_arm_feedback_20261028/detour_directions.json').read_text('utf8')) if r['frame']==216)['head_outward'];scene=bpy.context.scene;scene.frame_set(216);bpy.context.view_layer.update();localnormal=np.linalg.inv(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)[:3,:3])@direction
if options.direction!='head':
 direction={'side':[-1.,0,0],'up':[0.,0,1.],'front':[0,-1.,0],'back':[0,1.,0],'upback':[0,1.,1.]}[options.direction];direction=np.asarray(direction);direction/=np.linalg.norm(direction);localnormal=np.linalg.inv(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix)[:3,:3])@direction
profile=dict(p,pairs=[])
for a,b in p['pairs']:
 if a in ('arm.R','hand.R'):profile['pairs'].append([a,b])
 elif b in ('arm.R','hand.R'):profile['pairs'].append([b,a])
moving=np.array(sorted(set(parts['ids']['arm.R'])|set(parts['ids']['hand.R'])));guide=np.asarray(env['guide'])[:4];radii=np.asarray(env['radii'])[:4];bind=np.asarray(env['anchor_bind_matrix']);allbones=[arm.pose.bones[n] for n in chain];rows=[];static={b.name:(b.location.copy(),b.scale.copy()) for b in allbones}
for amount in (.04,.06,.08,.10):
 for swivel in (0.,):
  preserve=1.
  samples=[]
  for f in np.arange(214,226.01,1.):
   for b in allbones:b.location=static[b.name][0];b.scale=static[b.name][1]
   scene.frame_set(int(f));bpy.context.view_layer.update();before={b.name:b.rotation_quaternion.copy() for b in allbones};matrix=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);n=matrix[:3,:3]@localnormal;n/=np.linalg.norm(n);weight=smooth_detour(f,206,234);target=np.array(arm.matrix_world@allbones[2].head)+n*amount*weight;result=apply_two_bone_goal(arm,chain,target,preserve,swivel*weight);co=coords(mesh);delta=matrix@np.linalg.inv(bind);g=guide@delta[:3,:3].T+delta[:3,3];gap,_=capsule_features(co[moving],g,radii);regiongaps={r:float(capsule_features(co[parts['ids'][r]],g,radii)[0].min()) for r in ('arm.R','hand.R')};audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=3000);rotations={b.name:float(np.degrees(before[b.name].rotation_difference(b.rotation_quaternion).angle)) for b in allbones};samples.append({'frame':float(f),'gap_m':float(gap.min()),'region_gaps':regiongaps,'body_crossings':audit['ordinary_crossings'],'rotation_degrees':max(rotations.values()),'rotations':rotations,**result})
  row={'amplitude_m':amount,'swivel_radians':swivel,'preserve_wrist':preserve,'min_gap_m':min(r['gap_m'] for r in samples),'min_region_gaps':{r:min(x['region_gaps'][r] for x in samples) for r in ('arm.R','hand.R')},'body_crossings':sum(r['body_crossings'] for r in samples),'max_rotation_degrees':max(r['rotation_degrees'] for r in samples),'max_endpoint_error_m':max(r['endpoint_error_m'] for r in samples),'max_translation_error':max(r['local_translation_error'] for r in samples),'max_scale_error':max(r['local_scale_error'] for r in samples),'samples':samples};rows.append(row);(out/'route_search.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8');print('ARM_DETOUR_TRIAL',json.dumps({k:v for k,v in row.items() if k!='samples'}),flush=True)
print('ARM_DETOUR_SEARCH_COMPLETE',flush=True)
