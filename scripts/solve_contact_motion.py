"""Create a separate arm-contact action; never reuse the old cloth caches."""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,contacts,compact
p=argparse.ArgumentParser();p.add_argument('--frames',type=int,nargs='*');p.add_argument('--start',type=int,default=47);p.add_argument('--end',type=int,default=496);p.add_argument('--iterations',type=int,default=18);p.add_argument('--margin',type=float,default=.010);p.add_argument('--label',default='prototype');p.add_argument('--resume');p.add_argument('--warm',action='store_true');p.add_argument('--preserve-hand-orientation',action='store_true');p.add_argument('--limit-degrees',type=float,default=32);p.add_argument('--analytic-forward',type=float,default=0);p.add_argument('--analytic-up',type=float,default=0);p.add_argument('--analytic-separation',type=float,default=0);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend';bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];scene=bpy.context.scene
visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for o in visibility:o.hide_viewport=True
regions=skin_regions(body,arm);hands=add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);solver=ArmContactProjector(body,arm,regions,a.margin,limit_degrees=a.limit_degrees,preserve_hand_orientation=a.preserve_hand_orientation)
out=ROOT/'outputs/cynical_cloth15/contact_motion'/a.label;out.mkdir(parents=True,exist_ok=True)
original=arm.animation_data.action;original.use_fake_user=True;corrected=original.copy();corrected.use_fake_user=True;corrected.name='Cynical_ContactCorrected_'+a.label
report=dict(source=str(source),original_action=original.name,corrected_action=corrected.name,margin_m=a.margin,scope='Bounded arm/elbow/wrist optimization; no cloth solve, no CCD certificate',hands=hands,frames={});parameters=[];previous=None
reused={}
if a.resume:
    saved=Path(a.resume);reused={r['frame']:r['offsets'] for r in json.loads((saved/'offsets.json').read_text())};saved_report=json.loads((saved/'solve_report.json').read_text(encoding='utf-8'))
for frame in a.frames or range(a.start,a.end+1):
    arm.animation_data.action=original;scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();before=compact(contacts(body,arm,regions,a.margin,True))
    if frame in reused:
        x=np.array(reused[frame]);solver.apply(x);detail=saved_report['frames'][str(frame)]['after']
    else:
        initial=previous*.98 if a.warm and previous is not None else None
        if a.analytic_forward:
            from mathutils import Vector
            upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3();front=axes@Vector((0,-1,0));right=axes@Vector((1,0,0));up=axes@Vector((0,0,1));common=front.normalized()*a.analytic_forward+up.normalized()*a.analytic_up;initial=solver.hand_translation_seed([common+right.normalized()*a.analytic_separation,common-right.normalized()*a.analytic_separation])
        x,detail=solver.solve(initial=initial,iterations=a.iterations)
        if detail['remaining']['triangle_crossings']:
            alternative,other=solver.solve(iterations=a.iterations)
            if (other['remaining']['triangle_crossings'],np.linalg.norm(alternative))<(detail['remaining']['triangle_crossings'],np.linalg.norm(x)):x,detail=alternative,other
            solver.apply(x)
    previous=x.copy();row=dict(before=before,after=detail);parameters.append(dict(frame=frame,offsets=x.tolist()));report['frames'][str(frame)]=row
    rotations=[b.rotation_quaternion.copy() for b in solver.bones]
    arm.animation_data.action=corrected
    for b,q in zip(solver.bones,rotations):b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
    if before['triangle_crossings'] or detail['max_control_delta_deg']>.1:print('POSE_CONTACT',frame,before['triangle_crossings'],detail['remaining']['triangle_crossings'],detail['max_control_delta_deg'],flush=True)
    if frame%20==0:
        (out/'solve_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'offsets.json').write_text(json.dumps(parameters),encoding='utf-8')
arm.animation_data.action=corrected
paths={b.path_from_id('rotation_quaternion') for b in solver.bones}
for layer in corrected.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path in paths:
                    for key in curve.keyframe_points:
                        if a.start<=key.co.x<=a.end:key.interpolation='LINEAR'
(out/'solve_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(out/'offsets.json').write_text(json.dumps(parameters),encoding='utf-8')
for o,value in visibility.items():o.hide_viewport=value
for o in regions['extra_objects']:bpy.data.objects.remove(o,do_unlink=True)
# The pose has changed: old world-space PC2/CLOTH results are invalid. Hide the
# dynamic carrier while this standalone diagnostic action is reviewed.
for name in ('ClothShapePreservingTarget','ClothSimulationSurface','ClothUnskinnedVisualCarrier'):
    o=bpy.data.objects.get(name)
    if o:
        o.hide_render=True;o.hide_set(True)
for o in bpy.data.objects:
    for mod in o.modifiers:
        if mod.type in {'CLOTH','MESH_CACHE'} or (o.name=='Cloth' and mod.type=='NODES' and 'absolute' in mod.name.lower()):
            mod.show_viewport=False;mod.show_render=False
scene['contact_motion_status']='POSE_PROTOTYPE_REQUIRES_NEW_CLOTH_CACHE';scene.frame_set((a.frames or [47])[0]);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ContactMotion.blend'),compress=True)
print('CONTACT_MOTION_SAVED',str(out),flush=True)
