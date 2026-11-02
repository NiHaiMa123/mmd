"""Bake a sampled arm route as a removable absolute NLA layer and check it."""
import json
from pathlib import Path
import bpy,numpy as np
from .surface import coords,audit_frame
from .two_bone_contact_path import apply_two_bone_goal
from .arm_detour_planner import interpolate_waypoints
from .root_envelope_feedback import capsule_features
from .projector import FrameProjector
from .hair_track import add_layer
from .track import fcurves
from .exact_skin_collider import build_exact_skin_topology
from .closed_collider_field import ClosedColliderField


def bake_arm_route(mesh,arm,profile,parts,route,envelope,out,step=.25):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'bake_report.json').exists():raise ValueError('Use a new arm bake directory')
    first,last=float(route[0]['frame']),float(route[-1]['frame'])
    if any(w['start']<=last and w['end']>=first for w in profile.get('protected_windows',[])):raise ValueError('Arm route overlaps protected intentional contact')
    if len(profile['control_chains'])!=1 or arm.animation_data.action is not None:raise ValueError('Arm route baking requires one chain and the original motion in NLA')
    source=bpy.data.filepath;chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];scene=bpy.context.scene;count=int(envelope.get('root_guide_points',4));guide=np.asarray(envelope['guide'])[:count];radii=np.asarray(envelope['radii'])[:count];bind=np.asarray(envelope['anchor_bind_matrix']);moving=sorted({i for role in envelope['moving_regions'] for i in parts['ids'][role]});affected={b.name for b in arm.data.bones if b.name==chain[0] or chain[0] in {p.name for p in b.parent_recursive}};groups={g.index for g in mesh.vertex_groups if g.name in affected};outside=[v.index for v in mesh.data.vertices if not any(g.group in groups and g.weight>1e-7 for g in v.groups)];primary=profile.get('protected_bones') or sorted({n for role,names in profile['bone_roles'].items() if role in ('head','torso','leg.L','leg.R') for n in names});polish_profile=dict(profile,preserve_wrist_orientation=False,clearance_m=.001);polisher=FrameProjector(mesh,arm,polish_profile,parts,[chain],limit_degrees=3);polisher.bones=[bones[2]];polisher.n=3;previous=np.zeros(3);rows=[];poses=[];expected={};outside_checks={}
    attachments=np.asarray(envelope.get('attachment_points',[]),dtype=float)
    exact_mode=envelope.get('validation_mode')=='exact_attachment'
    if exact_mode and not len(attachments):raise ValueError('Exact attachment validation needs explicit fixed points')
    polisher.limit=np.radians(float(envelope.get('wrist_polish_degrees',3)))
    if len(attachments):skin_ids,skin_faces,skin_meta=build_exact_skin_topology(mesh,arm,profile)
    for frame in sorted(set([1.,first-.125,last+.125,450.]+[float(w[k]) for w in profile.get('protected_windows',[]) for k in ('start','end')])):
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();outside_checks[frame]=coords(mesh)
    for frame in np.arange(first,last+.001,step):
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();source_co=coords(mesh);local={b.name:(b.location.copy(),b.scale.copy()) for b in bones};old=[b.rotation_quaternion.copy() for b in bones];heading=(arm.matrix_world@bones[2].matrix).to_quaternion();primaries={n:np.array(arm.pose.bones[n].matrix) for n in primary};head=np.array(arm.matrix_world@arm.pose.bones[envelope['anchor_bone']].matrix);delta=head@np.linalg.inv(bind);g=guide@delta[:3,:3].T+delta[:3,3];waypoint=interpolate_waypoints(route,frame);goal=np.array(arm.matrix_world@bones[2].head)+waypoint[:3];detail=apply_two_bone_goal(arm,chain,goal,1.,waypoint[3]);polisher.capture()
        if all('wrist_polish' in r for r in route):
            times=[r['frame'] for r in route];values=np.asarray([r['wrist_polish'] for r in route]);previous=np.array([np.interp(frame,times,values[:,j]) for j in range(3)]);polisher.apply(previous)
        else:previous,polish=polisher.solve(initial=previous*.7,preferred=previous*.7,iterations=20)
        for b in bones:b.location=local[b.name][0];b.scale=local[b.name][1]
        arm.update_tag();bpy.context.view_layer.update();co=coords(mesh);audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=100000);gap,_=capsule_features(co[moving],g,radii);root_distance=None
        if len(attachments):field=ClosedColliderField(co[skin_ids],skin_faces);distance,_=field(attachments@delta[:3,:3].T+delta[:3,3]);root_distance=float(distance.min())
        rows.append({'frame':float(frame),'ordinary_body_crossings':audit['ordinary_crossings'],'ordinary_body_contained_samples':audit['ordinary_contained_samples'],'root_proxy_gap_m':float(gap.min()),'root_attachment_min_signed_m':root_distance,'wrist_offset_m':float(np.linalg.norm(waypoint[:3])),'wrist_heading_error_degrees':float(np.degrees(heading.rotation_difference((arm.matrix_world@bones[2].matrix).to_quaternion()).angle)),'rotation_degrees':dict(zip(chain,[float(np.degrees(q.rotation_difference(b.rotation_quaternion).angle)) for q,b in zip(old,bones)])),**detail});poses.append((float(frame),[b.rotation_quaternion.copy() for b in bones]));expected[float(frame)]={'co':co.copy(),'outside':source_co[outside].copy(),'primary':primaries}
    ad=arm.animation_data;action=bpy.data.actions.new('FixedAttachment_ArmAbsolute');action.use_fake_user=True;ad.action=action;continuity={}
    for frame,quaternions in poses:
        for b,q in zip(bones,quaternions):
            if b.name in continuity and q.dot(continuity[b.name])<0:q.negate()
            continuity[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name)
    for curve in fcurves(action):
        for key in curve.keyframe_points:key.interpolation='LINEAR'
    ad.action=None;strip=add_layer(arm,action,'Fixed hair attachment / arm detour','REPLACE',int(first),last);strip.extrapolation='NOTHING';layer_error=0.;unaffected_error=0.;primary_error=0.;outside_error=0.
    for frame,value in expected.items():
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();co=coords(mesh);layer_error=max(layer_error,float(np.max(np.abs(co-value['co']))));unaffected_error=max(unaffected_error,float(np.max(np.abs(co[outside]-value['outside']))));primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-matrix))) for n,matrix in value['primary'].items()))
    for frame,value in outside_checks.items():scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();outside_error=max(outside_error,float(np.max(np.abs(coords(mesh)-value))))
    result={'status':'ARM_ATTACHMENT_ROUTE_REQUIRES_INDEPENDENT_VALIDATION','source':source,'frames':[first,last],'step_frames':step,'chain':chain,'samples':rows,'body_failed_samples':sum(r['ordinary_body_crossings']>0 for r in rows),'proxy_failed_samples':sum(r['root_proxy_gap_m']<.003 for r in rows),'attachment_failed_samples':sum(r['root_attachment_min_signed_m'] is not None and r['root_attachment_min_signed_m']<float(envelope.get('attachment_clearance_m',.003)) for r in rows),'max_wrist_offset_m':max(r['wrist_offset_m'] for r in rows),'max_wrist_heading_error_degrees':max(r['wrist_heading_error_degrees'] for r in rows),'layer_error_m':layer_error,'unaffected_vertices_error_m':unaffected_error,'primary_matrix_error':primary_error,'outside_phase_error_m':outside_error,'original_actions_edited':False,'hair_resimulation_required':True}
    (out/'bake_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');assert layer_error<2e-6 and unaffected_error<2e-6 and primary_error<2e-6 and outside_error<2e-6,result
    result['validation_mode']='exact_attachment' if exact_mode else 'capsule_and_attachment'
    result['body_failed_samples']=sum(bool(r['ordinary_body_crossings'] or r['ordinary_body_contained_samples']) for r in rows)
    if exact_mode:
        result['capsule_diagnostic_failed_samples']=result['proxy_failed_samples'];result['proxy_failed_samples']=0
    (out/'bake_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    if result['body_failed_samples'] or result['proxy_failed_samples'] or result['attachment_failed_samples']:raise RuntimeError('Arm route failed subframe geometry checks')
    scene.frame_set(244);target=out/'Body_With_Attachment_Detour.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target),compress=True);result['candidate']=str(target);(out/'bake_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
