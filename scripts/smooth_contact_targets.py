"""Anticipatory bounded-speed hand targets and anatomical shoulder yielding."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector,Matrix,Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,contacts,compact
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/contact_motion/target_track_fast';bpy.ops.wm.open_mainfile(filepath=str(source/'ContactMotion.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];original=bpy.data.actions['シニカルナイトプラン_bone'];new=original.copy();new.name='Cynical_Contact_Anticipatory';new.use_fake_user=True
raw=json.loads((source/'target_report.json').read_text(encoding='utf-8'));profile=np.array([raw['frames'][str(i)]['target_distances_m']+[20. if raw['frames'][str(i)]['solve']['remaining']['triangle_crossings'] else 0.] for i in range(1,497)],dtype=float)
def envelope(values):
    result=values.copy();speed=np.array([.004,.003,.002,2.])
    for i in range(1,len(result)):result[i]=np.maximum(result[i],result[i-1]-speed)
    for i in range(len(result)-2,-1,-1):result[i]=np.maximum(result[i],result[i+1]-speed)
    return result
visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for o in visibility:o.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);solver=ArmContactProjector(body,arm,regions,.002,limit_degrees=60,preserve_hand_orientation=True);shoulders=[arm.pose.bones['肩.'+s] for s in ('L','R')];out=ROOT/'outputs/cynical_cloth15/contact_motion/anticipatory';out.mkdir(exist_ok=True);report=dict(method='minimum Lipschitz majorant of required clearance targets; same hand world orientations; two-link IK; shoulder rotations to gain reach',target_speed_limits_m_per_frame=[.004,.003,.002],shoulder_speed_limit_degrees_per_frame=2,not_ccd=True,passes=[])
for run in range(3):
    profile=envelope(profile);rows={};changes=0;residual=0;previous=None;result=[]
    for frame,parameters in enumerate(profile,1):
        arm.animation_data.action=original;scene.frame_set(frame);bpy.context.view_layer.update();source_rotations=[b.rotation_quaternion.copy() for b in solver.bones];shoulder_rotations=[b.rotation_quaternion.copy() for b in shoulders];hand_matrices=[arm.pose.bones['手首.'+s].matrix.copy() for s in ('L','R')];hand_positions=[arm.matrix_world@arm.pose.bones['手首.'+s].head for s in ('L','R')];upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3();front=(axes@Vector((0,-1,0))).normalized();right=(axes@Vector((1,0,0))).normalized();up=(axes@Vector((0,0,1))).normalized();best=None
        for attempt in range(5):
            chosen=parameters.copy()
            if attempt:chosen[3]=min(25,chosen[3]+5*attempt)
            if attempt>=3:chosen[:3]+=np.array([.015,.005,.005])*(attempt-2)
            for b,q in zip(solver.bones,source_rotations):b.rotation_quaternion=q
            for b,q in zip(shoulders,shoulder_rotations):b.rotation_quaternion=q
            arm.update_tag();bpy.context.view_layer.update()
            for i,b in enumerate(shoulders):
                axis=(arm.matrix_world@b.matrix).to_3x3().inverted()@up;b.rotation_quaternion=b.rotation_quaternion@Quaternion(axis,(-1 if i==0 else 1)*math.radians(chosen[3]))
            arm.update_tag();bpy.context.view_layer.update();solver.capture();solver.hand_matrices=[m.copy() for m in hand_matrices];common=front*chosen[0]+up*chosen[2];shift=[hand_positions[i]+common+right*chosen[1]*(1 if i==0 else -1)-(arm.matrix_world@solver.bones[i*3+2].head) for i in (0,1)]
            x=solver.hand_translation_seed(shift) if np.abs(chosen).max()>.00001 else np.zeros(18);x[6:9]=0;x[15:18]=0
            for i in range(6):
                part=x[3*i:3*i+3];length=np.linalg.norm(part)
                if length>solver.limit:part*=solver.limit/length
            solver.apply(x);audit=compact(contacts(body,arm,regions,.002,True,first_crossing=True,sample_contacts=False));rank=(audit['triangle_crossings'],attempt)
            state=([b.rotation_quaternion.copy() for b in solver.bones],[b.rotation_quaternion.copy() for b in shoulders])
            if best is None or rank<best[0]:best=(rank,chosen.copy(),state,audit)
            if not rank[0]:break
        rank,chosen,(quats,sq),audit=best
        if np.max(np.abs(chosen-profile[frame-1]))>1e-8:profile[frame-1]=chosen;changes+=1
        for b,q in zip(shoulders,sq):b.rotation_quaternion=q
        for b,q in zip(solver.bones,quats):b.rotation_quaternion=q
        arm.update_tag();bpy.context.view_layer.update();bones=solver.bones+shoulders;quats=quats+sq
        if previous:
            for q,old in zip(quats,previous):
                if q.dot(old)<0:q.negate()
        previous=[q.copy() for q in quats];arm.animation_data.action=new
        for b,q in zip(bones,quats):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
        rows[str(frame)]=dict(target=list(chosen),crossing_pairs_capped=audit['triangle_crossings']);residual+=bool(rank[0]);result.append(dict(frame=frame,quaternions=[list(q) for q in quats]))
        if frame%50==0:print('ANTICIPATORY_CONTACT',run,frame,rank[0],flush=True)
    report['passes'].append(dict(pass_index=run,profile_adjustments=changes,residual_frames=residual));report['frames']=rows
    if not changes:break
paths={b.path_from_id('rotation_quaternion') for b in solver.bones+shoulders}
for layer in new.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path in paths:
                    for key in curve.keyframe_points:
                        if 1<=key.co.x<=496:key.interpolation='LINEAR'
for o in regions['extra_objects']:bpy.data.objects.remove(o,do_unlink=True)
for o,v in visibility.items():o.hide_viewport=v
(out/'target_profile.json').write_text(json.dumps(profile.tolist()),encoding='utf-8');(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'poses.json').write_text(json.dumps(result),encoding='utf-8');scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ContactMotion.blend'),compress=True);print('ANTICIPATORY_READY',report['passes'],flush=True)
