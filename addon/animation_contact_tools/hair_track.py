"""Continuation solve and separate NLA layers for hair/body contact experiments."""
import json,time
from pathlib import Path
import numpy as np
import bpy
from .surface import regions,audit_frame,coords
from .strain_hair import StrainHairProjector
from .projector import FrameProjector
from .track import fcurves

def add_layer(arm,action,label,blend,first,last):
    track=arm.animation_data.nla_tracks.new();track.name=label;strip=track.strips.new(label,first,action);strip.blend_type=blend;strip.extrapolation='HOLD';strip.frame_end=last
    if hasattr(strip,'action_slot') and action.slots:strip.action_slot=action.slots[0]
    return strip

def solve_hair_track(mesh,arm,profile,out,first=1,last=450,step=3):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);parts=regions(mesh,arm,profile);hp=dict(profile)
    if not hp.get('hair_collision_targets'):raise ValueError('Declare hair_collision_targets explicitly; head/root overlap is not implicitly accepted')
    hp['hair_analytic_jacobian']=True
    hair=StrainHairProjector(mesh,arm,hp,parts,limit_degrees=profile.get('hair_rotation_limit_degrees',30),max_active=18)
    bp=dict(profile,extra_contact_targets=['hair_root'],preserve_wrist_orientation=False)
    bp['pairs']=[pair for pair in profile['pairs'] if pair[0].startswith(('arm','hand'))]+[(r,'hair_root') for r in ('arm.L','arm.R','hand.L','hand.R')]
    body=FrameProjector(mesh,arm,bp,parts,profile['control_chains'],limit_degrees=profile.get('hair_arm_feedback_limit_degrees',15)) if profile.get('hair_allow_arm_feedback',False) else None
    frames=sorted(set(range(first,last+1,step))|{last}|set(profile.get('hair_extra_frames',[]))|{int(w[k]) for w in profile.get('protected_windows',[]) for k in ('start','end')});frames=[f for f in frames if first<=f<=last]
    hx=np.zeros(hair.n);bx=np.zeros(body.n) if body else None;rows=[];poses=[];references={};start=time.monotonic();ad=arm.animation_data;source_action=ad.action
    primary=profile.get('protected_bones',['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ']);primary=[n for n in primary if n in arm.pose.bones]
    skin_roles=[r for r in parts['ids'] if not r.startswith('hair') and r!='unmapped_body'];skin_ids=sorted({i for r in skin_roles for i in parts['ids'][r]})
    source_hair_quaternions=[b.rotation_quaternion.copy() for b in hair.bones]
    source_body_quaternions=[b.rotation_quaternion.copy() for b in body.bones] if body else []
    checkpoint=out/'pose_checkpoint.jsonl'
    if checkpoint.exists():raise ValueError('Choose a fresh output directory; preserve existing pose checkpoints')
    with checkpoint.open('w',encoding='utf8') as stream:stream.write(json.dumps({'hair_bones':[b.name for b in hair.bones],'body_bones':[b.name for b in body.bones] if body else [],'source':bpy.data.filepath})+'\n')
    for frame in frames:
        for bone,q in zip(hair.bones,source_hair_quaternions):bone.rotation_quaternion=q
        if body:
            for bone,q in zip(body.bones,source_body_quaternions):bone.rotation_quaternion=q
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();source=coords(mesh);source_matrices={n:np.array(arm.pose.bones[n].matrix) for n in primary};hair.capture()
        if body:body.capture()
        hair.apply(hx);details=[]
        locked=any(w['start']<=frame<=w['end'] for w in profile.get('protected_windows',[]))
        for iteration in range(3):
            if body:bx,br=body.solve(initial=bx*.95,preferred=bx*.95,iterations=25)
            else:br={'status':'BODY_FROZEN'}
            hx,hr=hair.solve(initial=hx,preferred=hx,iterations=45);details.append({'body':br,'hair':hr})
            if not hr['remaining_target_crossings'] and hr['edge_ratio_max']<1.10 and hr['edge_ratio_min']>.90:break
        result=coords(mesh);hair_q=[b.rotation_quaternion.copy() for b in hair.bones];body_q=[q.inverted()@b.rotation_quaternion for b,q in zip(body.bones,body.base)] if body else []
        poses.append((frame,hair_q,body_q));references[frame]={'coords':result.copy(),'primary':source_matrices,'protected_skin':source[skin_ids].copy() if locked else None}
        with checkpoint.open('a',encoding='utf8') as stream:stream.write(json.dumps({'frame':frame,'hair':[list(q) for q in hair_q],'body':[list(q) for q in body_q]})+'\n')
        row={'frame':frame,'details':details,'hair_target_crossings':hr['remaining_target_crossings'],'head_or_other_crossings':hr['remaining_other_crossings'],'max_edge_ratio':hr['edge_ratio_max'],'min_edge_ratio':hr['edge_ratio_min'],'body_feedback_degrees':br.get('max_control_delta_deg',0.),'locked':locked,'primary_error':max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in source_matrices.items())};rows.append(row)
        np.savez_compressed(out/'continuation_checkpoint.npz',last_frame=frame,hair_offsets=hx,body_offsets=bx if bx is not None else np.zeros(0))
        (out/'solve_samples.json').write_text(json.dumps({'status':'RUNNING','samples':rows},ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_TRACK_SAMPLE',frame,row['hair_target_crossings'],row['max_edge_ratio'],flush=True)
        if frame in profile.get('hair_extra_frames',[]):np.savez_compressed(out/f'keypose{frame:04}.npz',coordinates=result)
    # Build pose actions only after all source-frame evaluations have finished.
    ha=bpy.data.actions.new('HairContact_AbsoluteRotations');ha.use_fake_user=True;ba=bpy.data.actions.new('HairContact_ArmFeedbackDelta');ba.use_fake_user=True
    for frame,hqs,bqs in poses:
        ad.action=ha
        for b,q in zip(hair.bones,hqs):b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name)
        if body:
            ad.action=ba
            for b,q in zip(body.bones,bqs):
                if q.w<0:q.negate()
                b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name)
    for action in (ha,ba):
        for curve in fcurves(action):
            for key in curve.keyframe_points:key.interpolation='LINEAR'
    ad.action=source_action;ad.use_nla=True;add_layer(arm,ha,'Hair contact: rotations','REPLACE',first,last)
    if body:add_layer(arm,ba,'Hair contact: bounded arm feedback','COMBINE',first,last)
    error=0.;primary_error=0.;protected_error=0.
    for frame in frames:
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();co=coords(mesh);r=references[frame];error=max(error,float(np.max(np.abs(co-r['coords']))));primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in r['primary'].items()))
        if r['protected_skin'] is not None:protected_error=max(protected_error,float(np.max(np.abs(co[skin_ids]-r['protected_skin']))))
    result={'status':'HAIR_KEYPOSE_LAYER_CANDIDATE','samples':rows,'sample_step_frames':step,'frames':[first,last],'layer_max_error_m':error,'primary_bone_matrix_error':primary_error,'protected_skin_max_error_m':protected_error,'hair_action':ha.name,'body_action':ba.name if body else None,'seconds':time.monotonic()-start,'complete_hair_accepted':False}
    (out/'hair_track_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    bpy.context.scene.frame_set(first);bpy.ops.wm.save_as_mainfile(filepath=str(out/'HairContact_LayerCandidate_NotAccepted.blend'),compress=True)
    assert error<2e-5,error;assert primary_error<2e-6,primary_error;assert protected_error<1e-5,protected_error
    return result
