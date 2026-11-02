"""Non-destructive correction action above an untouched original NLA base."""
import json,math,time
from pathlib import Path
import numpy as np
import bpy
from .surface import audit_frame,coords
from .projector import FrameProjector,exp_quat

def fcurves(action):
    if hasattr(action,'fcurves'):return list(action.fcurves)
    return [c for layer in action.layers for strip in layer.strips for bag in strip.channelbags for c in bag.fcurves]

def protect_factor(frame,windows,fade=6):
    factor=1.
    for w in windows:
        if w['start']<=frame<=w['end']:return 0.
        if w['start']-fade<frame<w['start']:factor=min(factor,(w['start']-frame)/fade)
        if w['end']<frame<w['end']+fade:factor=min(factor,(frame-w['end'])/fade)
    return factor

def install_delta_nla(arm,original,delta,first,last,windows):
    ad=arm.animation_data;ad.action=None
    base_track=ad.nla_tracks.new();base_track.name='Contact: original motion (preserved)'
    start=float(original.frame_range[0]);base=base_track.strips.new('Original',int(start),original);base.blend_type='REPLACE';base.extrapolation='HOLD'
    if hasattr(base,'action_slot') and len(original.slots):base.action_slot=original.slots[0]
    correction_track=ad.nla_tracks.new();correction_track.name='Contact: ordinary collision delta'
    strip=correction_track.strips.new('Ordinary contact correction',first,delta);strip.blend_type='COMBINE';strip.extrapolation='NOTHING'
    if hasattr(strip,'action_slot') and len(delta.slots):strip.action_slot=delta.slots[0]
    strip.use_animated_influence=True
    for f in range(first,last+1):strip.influence=protect_factor(f,windows);strip.keyframe_insert('influence',frame=f)
    for c in strip.fcurves:
        for k in c.keyframe_points:k.interpolation='LINEAR'
    ad.action_blend_type='REPLACE';ad.use_nla=True
    return strip

def solve_track(mesh,arm,profile,parts,out,first=1,last=450):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);ad=arm.animation_data
    if ad is None or ad.action is None or len(ad.nla_tracks):raise ValueError('Supply an armature with one active reference action and no pre-existing NLA stack')
    original=ad.action;original.use_fake_user=True;controls=profile['control_chains'];solver=FrameProjector(mesh,arm,profile,parts,controls)
    values=[];rows=[];previous=np.zeros(solver.n);reference={};protected={};start=time.monotonic()
    protected_bones=profile.get('protected_bones',['頭','上半身3','下半身','左足ＩＫ','右足ＩＫ'])
    for frame in range(first,last+1):
        ad.action=original;bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solver.capture()
        reference[frame]={n:np.array(arm.pose.bones[n].matrix) for n in protected_bones if n in arm.pose.bones}
        locked=any(w['start']<=frame<=w['end'] for w in profile.get('protected_windows',[]))
        if locked:protected[frame]=coords(mesh).copy()
        before=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
        initial=previous*(.985 if before['ordinary_crossings'] else .75)
        x,report=solver.solve(initial=initial,preferred=previous,iterations=20);previous=x.copy();values.append(x)
        rows.append({'frame':frame,'before_crossings':before['ordinary_crossings'],**report})
        if frame%30==1:print('CONTACT_TRACK_SOLVE',frame,report.get('remaining_crossings'),flush=True)
    # Symmetric short-window smoothing, followed by independent final surface
    # validation. Failed samples remain explicit, never hidden by this filter.
    values=np.array(values);smoothed=values.copy()
    for i in range(len(values)):
        ids=np.arange(max(0,i-2),min(len(values),i+3));w=np.exp(-.5*((ids-i)/1.)**2);smoothed[i]=np.average(values[ids],axis=0,weights=w)
        if any(z['start']<=first+i<=z['end'] for z in profile.get('protected_windows',[])):smoothed[i]=0
    delta=bpy.data.actions.new('OrdinaryContact_Delta');delta.use_fake_user=True;corrected=[];allbones=[arm.pose.bones[n] for chain in controls for n in chain]
    for i,frame in enumerate(range(first,last+1)):
        ad.action=original;bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();base=[b.rotation_quaternion.copy() for b in allbones]
        x,detail=solver.solve(initial=smoothed[i],preferred=smoothed[i],iterations=10)
        if detail.get('remaining_crossings',0):
            alternative,other=solver.solve(preferred=smoothed[i],iterations=28)
            if other.get('remaining_crossings',10**9)<detail.get('remaining_crossings',10**9):x,detail=alternative,other
            solver.apply(x)
        qdelta=[]
        for b,q0 in zip(allbones,base):
            q=q0.inverted()@b.rotation_quaternion
            if q.w<0:q.negate()
            qdelta.append(q)
        ad.action=delta
        for b,q in zip(allbones,qdelta):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
        corrected.append({'frame':frame,'offsets':x.tolist(),'surface_result_before_layering':detail})
        if frame%50==1:print('CONTACT_DELTA_BAKE',frame,flush=True)
    for c in fcurves(delta):
        for k in c.keyframe_points:k.interpolation='LINEAR'
    install_delta_nla(arm,original,delta,first,last,profile.get('protected_windows',[]))
    validations=[];protected_error=0.;primary_error=0.
    for frame in range(first,last+1):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        for n,m in reference[frame].items():primary_error=max(primary_error,float(np.max(np.abs(np.array(arm.pose.bones[n].matrix)-m))))
        if frame in protected:protected_error=max(protected_error,float(np.max(np.abs(coords(mesh)-protected[frame]))))
        audit=audit_frame(mesh,arm,profile,parts,hair=False,cap=2000)
        validations.append({'frame':frame,'ordinary_crossings':audit['ordinary_crossings'],'deferred_crossings':audit['deferred_crossings']})
    unresolved=[r for r in validations if r['ordinary_crossings']]
    result={'status':'BODY_ACTION_SAMPLED_PASS' if not unresolved else 'BODY_ACTION_PARTIAL_UNRESOLVED',
      'original_action':original.name,'correction_action':delta.name,'original_action_channels_edited':False,
      'protected_mesh_max_error_m':protected_error,'primary_bone_matrix_error':primary_error,
      'protected_windows':profile.get('protected_windows',[]),'frames':[first,last],
      'unresolved_frames':unresolved,'source_crossings_sum':sum(r['before_crossings'] for r in rows),
      'result_crossings_sum':sum(r['ordinary_crossings'] for r in validations),'discrete_not_ccd':True,
      'seconds':time.monotonic()-start,'solve':rows,'bake':corrected,'validation':validations}
    (out/'body_track_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    np.save(out/'correction_offsets.npy',smoothed)
    assert primary_error<2e-6,primary_error
    # Blender's NLA quaternion evaluation normalizes float32 channels; a few
    # micrometres of accumulated skinning roundoff is not a gesture change.
    assert protected_error<1e-5,protected_error
    return result
