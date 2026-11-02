"""Test a feasible discrete path in joint space rather than a Cartesian chord."""
import json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords,audit_frame
from animation_contact_tools.attachment_contact import attachment_contacts
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.hair_track import add_layer
from animation_contact_tools.track import fcurves
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';directory=root/'left_arm_feedback_refined';out=root/'left_joint_space_route';out.mkdir(exist_ok=True);source=json.loads((directory/'source.json').read_text('utf8'))['source'];profile=json.loads((directory/'profile.json').read_text('utf8'));envelope=json.loads((directory/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');attachments=initial['coordinates'][initial['pinned']];envelope['attachment_points']=attachments.tolist();bind=np.asarray(envelope['anchor_bind_matrix']);route=json.loads((directory/'planned_route.json').read_text('utf8'))['waypoints'];times=np.array([r['frame'] for r in route]);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];parts=regions(mesh,arm,profile);chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];skin_ids,skin_faces,meta=build_exact_skin_topology(mesh,arm,profile,triangulate=True);polisher=FrameProjector(mesh,arm,dict(profile,preserve_wrist_orientation=False,clearance_m=.001),parts,[chain],limit_degrees=3);polisher.bones=[bones[2]];polisher.n=3;rows=[];poses=[]
for f in np.arange(238.,250.001,.125):
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();old=[b.rotation_quaternion.copy() for b in bones];heading=(arm.matrix_world@bones[2].matrix).to_quaternion();local=[(b.location.copy(),b.scale.copy()) for b in bones];index=min(len(times)-2,max(0,int(np.searchsorted(times,f,side='right')-1)));u=(f-times[index])/(times[index+1]-times[index]);delta=np.array(arm.matrix_world@arm.pose.bones[envelope['anchor_bone']].matrix)@np.linalg.inv(bind)
 for j,b in enumerate(bones):b.rotation_quaternion=old[j]@Quaternion(route[index]['correction'][j]).slerp(Quaternion(route[index+1]['correction'][j]),u)
 arm.update_tag();bpy.context.view_layer.update();world=heading.to_matrix().to_4x4();world.translation=arm.matrix_world@bones[2].head;bones[2].matrix=arm.matrix_world.inverted()@world
 for b,(loc,scale) in zip(bones,local):b.location=loc;b.scale=scale
 arm.update_tag();bpy.context.view_layer.update();audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=100000)
 if audit['ordinary_crossings'] or audit['ordinary_contained_samples']:polisher.capture();polisher.solve(iterations=24)
 co=coords(mesh);audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=100000);contact=attachment_contacts(co,skin_ids,skin_faces,attachments@delta[:3,:3].T+delta[:3,3],.003);row={'frame':float(f),'root_min_distance_m':contact['minimum_distance'],'body_crossings':audit['ordinary_crossings'],'body_contained_samples':audit['ordinary_contained_samples'],'heading_delta_degrees':float(np.degrees(heading.rotation_difference((arm.matrix_world@bones[2].matrix).to_quaternion()).angle))};rows.append(row);poses.append((float(f),[b.rotation_quaternion.copy() for b in bones]));print('JOINT_SPACE_CHECK',json.dumps(row),flush=True)
ad=arm.animation_data;action=bpy.data.actions.new('JointSpace_ArmAbsolute');ad.action=action;continuity={}
for f,qs in poses:
 for b,q in zip(bones,qs):
  if b.name in continuity and q.dot(continuity[b.name])<0:q.negate()
  continuity[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=f,group=b.name)
for curve in fcurves(action):
 for k in curve.keyframe_points:k.interpolation='LINEAR'
ad.action=None;strip=add_layer(arm,action,'Joint-space hair root detour','REPLACE',238,250);strip.extrapolation='NOTHING';bpy.context.scene.frame_set(244);candidate=out/'JointSpace_Arm_NotAccepted.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True)
report={'status':'JOINT_SPACE_CANDIDATE_REQUIRES_VALIDATION','source':source,'candidate':str(candidate),'frames':[238,250],'samples':rows,'body_failed_samples':sum(bool(r['body_crossings'] or r['body_contained_samples']) for r in rows),'root_penetration_samples':sum(r['root_min_distance_m']<0 for r in rows),'min_root_distance_m':min(r['root_min_distance_m'] for r in rows),'max_heading_delta_degrees':max(r['heading_delta_degrees'] for r in rows),'original_actions_edited':False}
for name,data in [('report.json',report),('profile.json',profile),('envelope.json',envelope),('source.json',{'source':source})]:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print('JOINT_SPACE_COMPLETE',json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)
