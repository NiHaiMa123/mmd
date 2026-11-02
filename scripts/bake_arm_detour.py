import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.arm_detour_planner import interpolate_waypoints
from animation_contact_tools.root_envelope_feedback import capsule_features
from animation_contact_tools.two_bone_contact_path import apply_two_bone_goal
from animation_contact_tools.hair_track import add_layer
from animation_contact_tools.track import fcurves
from animation_contact_tools.projector import FrameProjector
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['linear','pchip'],default='pchip');parser.add_argument('--tag');a=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';folder=base/'hair_arm_feedback_20261028';out=folder/(a.tag or 'baked_'+a.mode);out.mkdir(exist_ok=True);route=json.loads((folder/'planned_route/planned_route.json').read_text('utf8'))['waypoints'];env=json.loads((folder/'root_contact_diagnosis.json').read_text('utf8'));(out/'input_route.json').write_text(json.dumps(route,indent=2),encoding='utf8')
bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);chain=p['control_chains'][1];bones=[arm.pose.bones[n] for n in chain];static={b.name:(b.location.copy(),b.scale.copy()) for b in bones};moving=set(parts['ids']['arm.R'])|set(parts['ids']['hand.R']);outside=sorted(set(range(len(mesh.data.vertices)))-moving);primary=['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ'];profile=dict(p,pairs=[])
for x,y in p['pairs']:
 if x in ('arm.R','hand.R'):profile['pairs'].append([x,y])
 elif y in ('arm.R','hand.R'):profile['pairs'].append([y,x])
affected_bones={b.name for b in arm.data.bones if b.name==chain[0] or chain[0] in {parent.name for parent in b.parent_recursive}};affected_groups={g.index for g in mesh.vertex_groups if g.name in affected_bones};affected={v.index for v in mesh.data.vertices if any(g.group in affected_groups and g.weight>1e-7 for g in v.groups)};outside=sorted(set(range(len(mesh.data.vertices)))-affected)
guide=np.asarray(env['guide'])[:4];radii=np.asarray(env['radii'])[:4];bind=np.asarray(env['anchor_bind_matrix']);scene=bpy.context.scene;first=int(route[0]['frame']);last=int(route[-1]['frame']);poses=[];expected={};rows=[]
polish_profile=dict(profile,preserve_wrist_orientation=False,clearance_m=.001);polisher=FrameProjector(mesh,arm,polish_profile,parts,[chain],limit_degrees=3);polisher.bones=[bones[2]];polisher.n=3;previous=np.zeros(3)
for f in np.arange(first,last+.001,.25):
 for b in bones:b.location=static[b.name][0];b.scale=static[b.name][1]
 scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();source=coords(mesh);matrices={n:np.array(arm.pose.bones[n].matrix) for n in primary};before=[b.rotation_quaternion.copy() for b in bones];source_wrist=(arm.matrix_world@bones[2].matrix).to_quaternion();matrix=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);delta=matrix@np.linalg.inv(bind);g=guide@delta[:3,:3].T+delta[:3,3];waypoint=interpolate_waypoints(route,f,a.mode);target=np.array(arm.matrix_world@bones[2].head)+waypoint[:3];detail=apply_two_bone_goal(arm,chain,target,1.,waypoint[3]);polisher.capture();polisher.limit=np.radians(3);previous,polish=polisher.solve(initial=previous*.7,preferred=previous*.7,iterations=20)
 if polish.get('remaining_crossings',0):polisher.limit=np.radians(5);previous,polish=polisher.solve(initial=previous,preferred=previous,iterations=25)
 co=coords(mesh);gap,_=capsule_features(co[sorted(moving)],g,radii);audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=5000);rotation=[float(np.degrees(q.rotation_difference(b.rotation_quaternion).angle)) for q,b in zip(before,bones)];heading=float(np.degrees(source_wrist.rotation_difference((arm.matrix_world@bones[2].matrix).to_quaternion()).angle));rows.append({'frame':float(f),'root_gap_m':float(gap.min()),'body_crossings':audit['ordinary_crossings'],'rotations_degrees':rotation,'wrist_world_heading_error_degrees':heading,'wrist_polish_degrees':float(np.degrees(np.linalg.norm(previous))),**detail});poses.append((float(f),[b.rotation_quaternion.copy() for b in bones]));expected[float(f)]={'coordinates':co.copy(),'source_outside':source[outside].copy(),'primary':matrices}
ad=arm.animation_data;action=bpy.data.actions.new('HairRoot_RightArm_Absolute');action.use_fake_user=True;old=ad.action;ad.action=action
previous={}
for f,quaternions in poses:
 for b,q in zip(bones,quaternions):
  if b.name in previous and q.dot(previous[b.name])<0:q.negate()
  previous[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=f,group=b.name)
for c in fcurves(action):
 for k in c.keyframe_points:k.interpolation='LINEAR'
ad.action=old;strip=add_layer(arm,action,'Hair root: planned right arm detour','REPLACE',first,last);strip.extrapolation='NOTHING';layer_error=0.;outside_error=0.;primary_error=0.
for f,e in expected.items():
 scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);layer_error=max(layer_error,float(np.max(np.abs(co-e['coordinates']))));outside_error=max(outside_error,float(np.max(np.abs(co[outside]-e['source_outside']))));primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in e['primary'].items()))
result={'status':'ARM_DETOUR_REQUIRES_HAIR_RESIMULATION','mode':a.mode,'frames':[first,last],'samples':rows,'min_root_gap_m':min(r['root_gap_m'] for r in rows),'body_failed_samples':sum(r['body_crossings']>0 for r in rows),'envelope_failed_samples':sum(r['root_gap_m']<.002 for r in rows),'max_rotation_degrees_by_bone':dict(zip(chain,np.max([r['rotations_degrees'] for r in rows],axis=0).tolist())),'layer_error_m':layer_error,'unaffected_vertices_error_m':outside_error,'primary_matrix_error':primary_error,'original_actions_edited':False,'wrist_world_heading_error_degrees':max(r['wrist_world_heading_error_degrees'] for r in rows),'wrist_polish_limit_degrees':5,'bone_stretch_used':False,'action':action.name,'complete_hair_accepted':False}
(out/'arm_detour_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');assert layer_error<2e-5,layer_error;assert outside_error<2e-6,outside_error;assert primary_error<2e-6,primary_error
scene.frame_set(218);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Body_With_ArmDetour.blend'),compress=True);print('ARM_DETOUR_BAKED',json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
