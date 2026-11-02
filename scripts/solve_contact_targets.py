"""Contact-aware hand target paths: preserve gestures and let elbows yield."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,smooth_offset_track,contacts,compact
FAST='--fast' in sys.argv
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];original=arm.animation_data.action;original.use_fake_user=True;new=original.copy();new.use_fake_user=True;new.name='Cynical_Contact_HandTargets'
visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for o in visibility:o.hide_viewport=True
regions=skin_regions(body,arm);hands=add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);solver=ArmContactProjector(body,arm,regions,.010,limit_degrees=60,preserve_hand_orientation=True)
known=json.loads((ROOT/'outputs/cynical_cloth15/contact_motion/sequence_v5/temporal/dense_contact_qa.json').read_text(encoding='utf-8'))['frames']['before'];profiles=[]
for frame in range(1,497):
    row=known.get(str(frame))
    if row is None:scene.frame_set(frame);row=compact(contacts(body,arm,regions,.002,True))
    forward=separate=up=0.
    for pair in row['pairs']:
        if not(pair['triangle_crossings'] or pair['penetrating_samples']):continue
        depth=max(0,-(pair['min_local_gap_m'] or 0))
        if pair['pair']==['arm.L','arm.R']:separate=max(separate,min(.045,max(.025,.5*depth+.012)));up=.010
        elif pair['pair'][0].startswith('arm'):forward=max(forward,min(.115,max(.025,depth+.02)))
    profiles.append([forward,separate,up])
profile=smooth_offset_track(np.array(profiles),radius=12,sigma=4);report=dict(method='contact-derived hand target translations, look-ahead smoothing, two-link IK seed, gesture-orientation preservation, evaluated-skin contact projection',hands=hands,frames={},not_ccd=True);result=[];previous_q=None;out=ROOT/'outputs/cynical_cloth15/contact_motion'/('target_track_fast' if FAST else 'target_track');out.mkdir(exist_ok=True)
for frame,distances in enumerate(profile,1):
    arm.animation_data.action=original;scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3();front=(axes@Vector((0,-1,0))).normalized();right=(axes@Vector((1,0,0))).normalized();up=(axes@Vector((0,0,1))).normalized();best=None
    for attempt in range(8 if FAST else 4):
        f,s,u=distances+np.array([attempt*.015,attempt*.01,attempt*.005]);common=front*f+up*u;initial=solver.hand_translation_seed([common+right*s,common-right*s]) if max(abs(f),abs(s),abs(u))>.0001 else None
        if FAST:
            x=np.zeros(18) if initial is None else initial.copy();x[6:9]=0;x[15:18]=0
            for j in range(6):
                part=x[j*3:j*3+3];length=np.linalg.norm(part)
                if length>solver.limit:part*=solver.limit/length
            solver.apply(x);check=compact(contacts(body,arm,regions,.002,True));detail=dict(iterations=[],remaining=check,max_control_delta_deg=float(np.linalg.norm(x.reshape(6,3),axis=1).max()*180/math.pi),analytic_seed_only=True)
        else:x,detail=solver.solve(initial=initial,iterations=22)
        rank=(detail['remaining']['triangle_crossings'],attempt)
        if best is None or rank<best[0]:best=(rank,x.copy(),detail,(f,s,u))
        if rank[0]==0 and (not FAST or detail['remaining']['penetrating_samples']==0):break
    if FAST and best[0][0]:
        _,seed,_,used=best;x,detail=solver.solve(initial=seed,iterations=22)
        if detail['remaining']['triangle_crossings']<best[0][0]:best=((detail['remaining']['triangle_crossings'],0),x.copy(),detail,used)
    _,x,detail,used=best;solver.apply(x);quats=[b.rotation_quaternion.copy() for b in solver.bones]
    if previous_q:
        for q,old in zip(quats,previous_q):
            if q.dot(old)<0:q.negate()
    previous_q=[q.copy() for q in quats];orientation_error=max((solver.bones[i].matrix.to_quaternion().rotation_difference(solver.hand_matrices[g].to_quaternion())).angle for g,i in enumerate((2,5)))
    arm.animation_data.action=new
    for b,q in zip(solver.bones,quats):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
    report['frames'][str(frame)]=dict(solve=detail,target_distances_m=list(used),hand_orientation_error_degrees=orientation_error*180/math.pi);result.append(dict(frame=frame,offsets=x.tolist(),quaternions=[list(q) for q in quats]))
    if frame%25==0:print('HAND_TARGET_CONTACT',frame,detail['remaining']['triangle_crossings'],list(used),flush=True);(out/'target_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
paths={b.path_from_id('rotation_quaternion') for b in solver.bones}
for layer in new.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path in paths:
                    for key in curve.keyframe_points:
                        if 1<=key.co.x<=496:key.interpolation='LINEAR'
for o in regions['extra_objects']:bpy.data.objects.remove(o,do_unlink=True)
for o,v in visibility.items():o.hide_viewport=v
for o in bpy.data.objects:
    for mod in o.modifiers:
        if mod.type in {'CLOTH','MESH_CACHE'} or (o.name=='Cloth' and mod.type=='NODES' and 'absolute' in mod.name.lower()):mod.show_viewport=False;mod.show_render=False
scene['contact_motion_status']='HAND_TARGET_PROTOTYPE_REQUIRES_NEW_CLOTH_CACHE';scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ContactMotion.blend'),compress=True);(out/'target_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'offsets.json').write_text(json.dumps(result),encoding='utf-8');print('HAND_TARGET_TRACK_READY',str(out),flush=True)
