"""Smooth bounded arm feedback around an explicitly anchored hair-root envelope.

The capsule envelope is conservative. Visible hair must be re-simulated and
audited afterward. This does not automatically rebuild intentional contacts.
"""
import math,json,time
from pathlib import Path
import numpy as np
import bpy
from .surface import coords,audit_frame
from .projector import FrameProjector
from .track import fcurves
from .hair_track import add_layer


def cubic_basis(frame,centres,width):
    t=np.abs((frame-np.asarray(centres,dtype=float))/width)
    return np.where(t<1,2/3-t*t+.5*t*t*t,np.where(t<2,(2-t)**3/6,0.))


def capsule_features(vertices,guide,radii):
    start=guide[:-1];d=guide[1:]-start;u=np.clip(np.einsum('vsi,si->vs',vertices[:,None,:]-start[None,:,:],d)/np.maximum(np.sum(d*d,axis=1),1e-15),0,1)
    q=start+u[:,:,None]*d;r=radii[:-1]+u*(radii[1:]-radii[:-1]);delta=vertices[:,None,:]-q;distance=np.linalg.norm(delta,axis=2);gaps=distance-r;chosen=np.argmin(gaps,axis=1);row=np.arange(len(vertices));normal=delta[row,chosen]/np.maximum(distance[row,chosen,None],1e-12)
    return gaps[row,chosen],normal


def solve_root_feedback(mesh,arm,profile,parts,envelope,out,centres=(212,218,224),width=6.,limit_degrees=10,iterations=24):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    if arm.animation_data is None or arm.animation_data.action is not None:raise ValueError('Provide a preserved NLA source stack with no active Action above the new feedback layer')
    anchor=envelope['anchor_bone'];rest=np.asarray(envelope['guide'],dtype=float);radii=np.asarray(envelope['radii'],dtype=float)
    count=int(envelope.get('root_segments',3));rest=rest[:count+1];radii=radii[:count+1];bind=np.asarray(envelope['anchor_bind_matrix']);units=float(profile.get('units_to_m',1.))
    if units!=1.:raise ValueError('Root-envelope experiment currently uses metre world coordinates')
    bp=dict(profile,preserve_wrist_orientation=True);solver=FrameProjector(mesh,arm,bp,parts,profile['control_chains'],limit_degrees=limit_degrees)
    moving=sorted({i for r in envelope['moving_regions'] for i in parts['ids'][r]});moving=np.array(moving,dtype=int)
    start=math.floor(min(centres)-2*width);end=math.ceil(max(centres)+2*width)
    if any(not(w['end']<start or w['start']>end) for w in profile.get('protected_windows',[])):raise ValueError('Feedback support intersects a protected intentional-contact window')
    sample_frames=np.arange(start,end+.01,.5);states=[];scene=bpy.context.scene
    for frame in sample_frames:
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();solver.capture();delta=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix)@np.linalg.inv(bind)
        states.append({'frame':float(frame),'base':[q.copy() for q in solver.base],'wrist_base':[q.copy() for q in solver.wrist_base],'hand_frames':[m.copy() for m in solver.hand_frames],
            'guide':rest@delta[:3,:3].T+delta[:3,3],'basis':cubic_basis(frame,centres,width)})
    coefficients=np.zeros((len(centres),solver.n));history=[];body_weight=float(profile.get('root_body_constraint_weight',4.))
    fixed_normal=envelope.get('avoidance_normal_anchor_local')
    if fixed_normal is not None:
        for state in states:
            scene.frame_set(int(state['frame']),subframe=state['frame']%1);bpy.context.view_layer.update();rotation=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix)[:3,:3];n=rotation@np.asarray(fixed_normal);state['normal']=n/np.linalg.norm(n)
    def activate(state,coeff):
        f=state['frame'];scene.frame_set(int(f),subframe=f%1);solver.base=state['base'];solver.wrist_base=state['wrist_base'];solver.hand_frames=state['hand_frames'];solver.apply(state['basis']@coeff)
        return coords(mesh)
    def bounded(coeff):
        result=coeff.copy()
        for i in range(len(result)):result[i]=solver.bounded(result[i])
        return result
    for iteration in range(iterations):
        blocks=[];rhs=[];sets=[];worst=1.;body_crossings=0
        for state in states:
            co=activate(state,coefficients);gaps,normals=capsule_features(co[moving],state['guide'],radii);worst=min(worst,float(gaps.min()));bad=np.flatnonzero(gaps<profile['clearance_m'])
            if len(bad)>180:bad=bad[np.argsort(gaps[bad])[:180]]
            rootids=moving[bad];rootnormals=normals[bad];rootbase=gaps[bad]
            if fixed_normal is not None:
                n=state['normal'];support=float(np.max(state['guide']@n+radii));rootnormals=np.tile(n,(len(bad),1));rootbase=co[rootids]@n-support
            audit=audit_frame(mesh,arm,bp,parts,hair=False,cap=2000);cs=solver.constraints(audit,co);body_crossings+=audit['ordinary_crossings'];bodybase=solver.features(co,cs).reshape(-1,3);bn=np.array([c[-2] for c in cs]).reshape(-1,3);bg=np.array([c[-1] for c in cs])
            if not len(bad) and not cs:continue
            features=np.r_[rootbase,bg];local=np.zeros((len(features),solver.n));x=state['basis']@coefficients
            for j in range(solver.n):
                pert=x.copy();pert[j]+=.001;solver.apply(pert);new=coords(mesh);local[:len(bad),j]=np.einsum('ij,ij->i',new[rootids]-co[rootids],rootnormals)/.001
                if cs:local[len(bad):,j]=np.einsum('ij,ij->i',solver.features(new,cs)-bodybase,bn)/.001
            solver.apply(x);weights=np.r_[np.ones(len(bad)),np.full(len(bg),body_weight)];global_jac=np.hstack([local*value for value in state['basis']]);blocks.append(global_jac*weights[:,None]);rhs.append((profile['clearance_m']-features)*weights)
            sets.append((state,rootids,rootnormals,rootbase,co[rootids].copy(),cs,bodybase,bn,bg))
        print('ROOT_FEEDBACK_ITER',iteration,round(worst*1000,3),body_crossings,len(sets),flush=True)
        if not sets:break
        J=np.vstack(blocks);b=np.concatenate(rhs);regularization=.0003
        step=np.linalg.solve(J.T@J+np.eye(J.shape[1])*regularization,J.T@b-regularization*coefficients.ravel()).reshape(coefficients.shape)
        # Scale the entire coupled trajectory step uniformly. Clipping each
        # coefficient/bone independently can reverse the descent direction
        # when two joints or spline coefficients compensate each other.
        largest=max(np.linalg.norm(row[j:j+3]) for row in step for j in range(0,len(row),3))
        if largest>np.radians(2):step*=np.radians(2)/largest
        old=float(np.maximum(b,0)@np.maximum(b,0));accepted=False
        print('ROOT_FEEDBACK_LINEAR',float(np.linalg.norm(J)),float(np.linalg.norm(step)),old,flush=True)
        for factor in (1,.5,.25,.1):
            candidate=bounded(coefficients+step*factor);score=0.
            for state,ids,n,g,oldco,cs,bodybase,bn,bg in sets:
                co=activate(state,candidate);gap=g+np.einsum('ij,ij->i',co[ids]-oldco,n);deficit=np.maximum(profile['clearance_m']-gap,0);score+=float(deficit@deficit)
                if cs:
                    gap=bg+np.einsum('ij,ij->i',solver.features(co,cs)-bodybase,bn);deficit=np.maximum(profile['clearance_m']-gap,0);score+=float(deficit@deficit)*body_weight**2
            print('ROOT_FEEDBACK_LINE',factor,score,flush=True)
            if score<old-1e-12:coefficients=candidate;accepted=True;break
        history.append({'iteration':iteration,'min_root_gap_m':worst,'body_crossings':body_crossings,'objective':old,'accepted':accepted})
        (out/'feedback_progress.json').write_text(json.dumps({'history':history,'coefficients':coefficients.tolist()},indent=2),encoding='utf8')
        if not accepted:break
    # Bake relative to the complete existing NLA stack; no source Action edits.
    allbones=[arm.pose.bones[n] for chain in profile['control_chains'] for n in chain];poses=[];references={};primary=[n for n in profile.get('protected_bones',['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ']) if n in arm.pose.bones]
    # Bake absolute local rotations at quarter frames. This avoids composition
    # drift above pre-existing COMBINE layers, while preserving their Actions
    # and every unkeyed bone. The support endpoints reproduce the source pose.
    for f in np.arange(start,end+.001,.25):
        scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();state={'frame':float(f),'base':[q.copy() for q in solver.base],'wrist_base':[q.copy() for q in solver.wrist_base],'hand_frames':[m.copy() for m in solver.hand_frames],'basis':cubic_basis(f,centres,width)}
        refs={n:np.array(arm.pose.bones[n].matrix) for n in primary};activate(state,coefficients)
        qdelta=[b.rotation_quaternion.copy() for b in allbones]
        for q in qdelta:
            if q.w<0:q.negate()
        poses.append((f,qdelta));references[f]={'coordinates':coords(mesh).copy(),'primary':refs}
    ad=arm.animation_data;original_action=ad.action;delta=bpy.data.actions.new('HairRoot_ArmFeedback_Delta');delta.use_fake_user=True;ad.action=delta
    for f,qs in poses:
        for bone,q in zip(allbones,qs):bone.rotation_quaternion=q;bone.keyframe_insert('rotation_quaternion',frame=f,group=bone.name)
    for curve in fcurves(delta):
        for key in curve.keyframe_points:key.interpolation='LINEAR'
    ad.action=original_action;strip=add_layer(arm,delta,'Hair roots: smooth arm feedback','REPLACE',start,end);strip.extrapolation='NOTHING'
    error=0.;primary_error=0.;rows=[]
    for state in states:
        f=state['frame'];scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);gaps,_=capsule_features(co[moving],state['guide'],radii);audit=audit_frame(mesh,arm,bp,parts,hair=False,cap=2000)
        rows.append({'frame':f,'min_root_gap_m':float(gaps.min()),'vertices_below_clearance':int(np.sum(gaps<profile['clearance_m']-.0001)),'body_crossings':audit['ordinary_crossings']})
        error=max(error,float(np.max(np.abs(co-references[f]['coordinates']))));primary_error=max(primary_error,max(float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))) for n,m in references[f]['primary'].items()))
    result={'status':'ROOT_ENVELOPE_CANDIDATE_REQUIRES_HAIR_RESIMULATION','action':delta.name,'frames':[start,end],'centres':list(centres),'basis_width':width,'coefficients':coefficients.tolist(),'limit_degrees':limit_degrees,'max_coeff_rotation_degrees':float(max(np.linalg.norm(row[j:j+3]) for row in coefficients for j in range(0,solver.n,3))*180/np.pi),'max_evaluated_control_degrees':float(max(np.linalg.norm((s['basis']@coefficients)[j:j+3]) for s in states for j in range(0,solver.n,3))*180/np.pi),'layer_error_m':error,'primary_matrix_error':primary_error,'samples':rows,'history':history,'seconds':time.monotonic()-started,'original_actions_edited':False,'preserved_wrist_orientation':True,'complete_hair_accepted':False}
    (out/'root_feedback_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');assert error<2e-5,error;assert primary_error<2e-6,primary_error
    return result
