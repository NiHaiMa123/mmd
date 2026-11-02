"""Smooth a complete correction track, then re-project actual contacts."""
import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,smooth_offset_track
p=argparse.ArgumentParser();p.add_argument('--fit',default='sequence_v5');p.add_argument('--iterations',type=int,default=18);p.add_argument('--preserve-hands',action='store_true');p.add_argument('--output',default='temporal');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=ROOT/'outputs/cynical_cloth15/contact_motion'/a.fit
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(folder/'ContactMotion.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];original=bpy.data.actions['シニカルナイトプラン_bone'];new=original.copy();new.name='Cynical_Contact_Temporal';new.use_fake_user=True
track=json.loads((folder/'offsets.json').read_text());values=np.array([r['offsets'] for r in track]);smooth=smooth_offset_track(values,radius=12 if a.preserve_hands else 5,sigma=4 if a.preserve_hands else 2);visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for o in visibility:o.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);solver=ArmContactProjector(body,arm,regions,.010,limit_degrees=45,preserve_hand_orientation=a.preserve_hands);out=folder/a.output;out.mkdir(exist_ok=True);report=dict(frames={},method='look-ahead Gaussian then evaluated-skin contact projection',preserve_hand_orientation=a.preserve_hands,not_ccd=True);result=[]
for i,row in enumerate(track):
    frame=row['frame'];arm.animation_data.action=original;scene.frame_set(frame);solver.capture();x,detail=solver.solve(initial=smooth[i],preferred=smooth[i],prior_weight=.0001,iterations=a.iterations)
    if detail['remaining']['triangle_crossings']:
        alternative,other=solver.solve(initial=values[i],preferred=smooth[i],prior_weight=.00005,iterations=a.iterations*2)
        if other['remaining']['triangle_crossings']<detail['remaining']['triangle_crossings']:x,detail=alternative,other
        solver.apply(x)
    q=[b.rotation_quaternion.copy() for b in solver.bones];arm.animation_data.action=new
    for b,rotation in zip(solver.bones,q):b.rotation_quaternion=rotation;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
    report['frames'][str(frame)]=detail;result.append(dict(frame=frame,offsets=x.tolist()))
    if frame%25==0:print('CONTACT_TEMPORAL',frame,detail['remaining']['triangle_crossings'],flush=True)
    if frame%50==0:(out/'polish_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
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
arr=np.array([r['offsets'] for r in result]);report['offset_velocity_before_deg_per_frame']=float(np.linalg.norm(np.diff(values,axis=0).reshape(-1,6,3),axis=2).max()*180/np.pi);report['offset_velocity_after_deg_per_frame']=float(np.linalg.norm(np.diff(arr,axis=0).reshape(-1,6,3),axis=2).max()*180/np.pi)
(out/'offsets.json').write_text(json.dumps(result),encoding='utf-8');(out/'polish_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ContactMotion.blend'),compress=True);print('CONTACT_TEMPORAL_READY',str(out),flush=True)
