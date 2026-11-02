"""Repair measured subframe contacts while preserving already valid poses."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,regions,audit_frame
from animation_contact_tools.hair_bundle_profile import resolve_bundle
from animation_contact_tools.hair_position_cache import bind_position_cache
from animation_contact_tools.projector import FrameProjector
from animation_contact_tools.hair_track import add_layer
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);p.add_argument('--step',type=float,default=.125);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'report.json').exists():raise ValueError('Use a fresh refinement directory')
r=json.loads((src/'report.json').read_text('utf8'));profile=r['rig_profile'];config=r['bundle'];first,last=r['frames'];engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['candidate'],load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];scene=bpy.context.scene;chain=profile['control_chains'][0];names=chain+profile.get('auxiliary_twist_bones',[]);bones=[arm.pose.bones[n] for n in names];bundle=resolve_bundle(mesh,arm,regions(mesh,arm,profile),config);initial=np.load(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle/left_rig_root_native/initial_projection.npz');scene.frame_set(1);bpy.context.view_layer.update();head0=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);frames=np.arange(first,last+.001,a.step);states=[];heads=[];hair=[]
for frame in frames:
 scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();head=np.array(arm.matrix_world@arm.pose.bones[config['anchor_bone']].matrix);delta=head@np.linalg.inv(head0);heads.append(head);hair.append(initial['coordinates']@delta[:3,:3].T+delta[:3,3]);states.append(dict(q=[b.rotation_quaternion.copy() for b in bones],loc=[b.location.copy() for b in bones],scale=[b.scale.copy() for b in bones]))
cache=bind_position_cache(mesh,bundle['ids'],hair,out/'ConservativeClump.pc2',first=first,anchor_armature=arm,anchor_bone=config['anchor_bone'],anchor_matrices=heads,sample_step=a.step);modifier=mesh.modifiers[-1];roles=[role for role,ns in profile['bone_roles'].items() if role.startswith(('arm','hand')) and any(n in ns for n in chain)];joint_profile=dict(profile,pairs=profile['pairs']+[[role,'hair_mobile'] for role in roles],extra_contact_targets=['hair_mobile'],preserve_wrist_orientation=True,clearance_m=.002);joint=FrameProjector(mesh,arm,joint_profile,bundle['parts'],[chain],limit_degrees=3.);wrist=FrameProjector(mesh,arm,dict(joint_profile,preserve_wrist_orientation=False),bundle['parts'],[chain],limit_degrees=3.);wrist.bones=[bones[2]];wrist.n=3;poses=[];rows=[]
for frame,state in zip(frames,states):
 scene.frame_set(int(frame),subframe=frame%1)
 for b,q,loc,scale in zip(bones,state['q'],state['loc'],state['scale']):b.rotation_quaternion=q;b.location=loc;b.scale=scale
 arm.update_tag();bpy.context.view_layer.update();before=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000);heading=(arm.matrix_world@bones[2].matrix).to_quaternion()
 if before['ordinary_crossings'] or before['ordinary_contained_samples']:
  joint.capture();joint.solve(iterations=36);after=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000)
  if after['ordinary_crossings'] or after['ordinary_contained_samples']:wrist.capture();wrist.solve(iterations=36)
 for b,loc,scale in zip(bones,state['loc'],state['scale']):b.location=loc;b.scale=scale
 arm.update_tag();bpy.context.view_layer.update();after=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000);row=dict(frame=float(frame),before_crossings=before['ordinary_crossings'],after_crossings=after['ordinary_crossings'],contained=after['ordinary_contained_samples'],wrist_heading_delta_degrees=float(np.degrees(heading.rotation_difference((arm.matrix_world@bones[2].matrix).to_quaternion()).angle)));rows.append(row);poses.append([b.rotation_quaternion.copy() for b in bones])
 if row['before_crossings']:print('CLUMP_SUBFRAME_REPAIR',json.dumps(row),flush=True)
mesh.modifiers.remove(modifier);mesh.data.attributes.remove(mesh.data.attributes[cache['selection_attribute']]);action=bpy.data.actions.new('Contact_ClumpDetour_SubframeRefinement');action.use_fake_user=True;ad=arm.animation_data;ad.action=action;previous={}
for frame,quaternions in zip(frames,poses):
 for b,q in zip(bones,quaternions):
  if b.name in previous and q.dot(previous[b.name])<0:q.negate()
  previous[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=float(frame),group=b.name)
for c in fcurves(action):
 for key in c.keyframe_points:key.interpolation='LINEAR'
ad.action=None;strip=add_layer(arm,action,'Subframe contact refinement','REPLACE',first,last);strip.extrapolation='NOTHING';scene.frame_set(245);candidate=out/'Body_ClumpDetour_SubframeRefined.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True);r.update(status='CLUMP_DETOUR_SUBFRAME_REPAIR_REQUIRES_INDEPENDENT_AUDIT',candidate=str(candidate),sample_step=a.step,sample_count=len(rows),samples=rows,source_refinement=str(src),failed_refinement_samples=sum(bool(x['after_crossings'] or x['contained']) for x in rows),maximum_additional_wrist_heading_degrees=max(x['wrist_heading_delta_degrees'] for x in rows));(out/'report.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print('CLUMP_SUBFRAME_COMPLETE',r['failed_refinement_samples'],r['maximum_additional_wrist_heading_degrees'],flush=True)
