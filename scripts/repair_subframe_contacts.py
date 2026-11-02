"""Repair verified between-key crossings; retain the best audited candidate."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,contacts,compact
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/contact_motion/sequence_v5/temporal';out=ROOT/'outputs/cynical_cloth15/contact_motion/body_contact_v1';out.mkdir(exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source/'ContactMotion.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];new=arm.animation_data.action.copy();new.name='Cynical_Contact_SubframeRepair';new.use_fake_user=True;arm.animation_data.action=new
visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for o in visibility:o.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);solver=ArmContactProjector(body,arm,regions,.003,limit_degrees=12);report=dict(source=str(source/'ContactMotion.blend'),repairs=[],local_samples={});frames=[323.5,324.5]
for turn in range(3):
    for f in sorted(set(frames)):
        scene.frame_set(int(f),subframe=f%1);before=compact(contacts(body,arm,regions,.002,True))
        if not before['triangle_crossings']:continue
        solver.capture();x,detail=solver.solve(iterations=28);quats=[b.rotation_quaternion.copy() for b in solver.bones]
        for b,q,base in zip(solver.bones,quats,solver.base):
            if q.dot(base)<0:q.negate()
            b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=f,group=b.name)
        report['repairs'].append(dict(frame=f,before=before,after=detail));print('SUBFRAME_CONTACT_REPAIR',f,before['triangle_crossings'],detail['remaining']['triangle_crossings'],flush=True)
    frames=[]
    for f in np.arange(322.5,326.51,.125):
        scene.frame_set(int(f),subframe=float(f%1));row=compact(contacts(body,arm,regions,.002,True));report['local_samples'][f'{f:g}']=row
        if row['triangle_crossings']:frames.append(float(f))
    if not frames:break
paths={b.path_from_id('rotation_quaternion') for b in solver.bones}
for layer in new.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                if fc.data_path in paths:
                    for kp in fc.keyframe_points:
                        if 1<=kp.co.x<=496:kp.interpolation='LINEAR'
for o in regions['extra_objects']:bpy.data.objects.remove(o,do_unlink=True)
for o,value in visibility.items():o.hide_viewport=value
report['remaining_local_crossing_samples']=len(frames);(out/'subframe_repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ContactMotion.blend'),compress=True);print('SUBFRAME_REPAIR_READY',len(frames),flush=True)
