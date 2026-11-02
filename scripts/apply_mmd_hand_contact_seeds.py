"""Apply contact seeds with actual MMD shoulder/elbow/wrist IK and skin audits.

Only static keypose regression. Existing motion/cloth caches are not accepted.
"""
import argparse,json,sys,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import skin_regions,add_glove_hands,ArmContactProjector,all_coords,evaluated_coords,triangle_crosses,PAIRS,HAND_PREFIX
p=argparse.ArgumentParser();p.add_argument('--seeds',required=True);p.add_argument('--output',required=True);p.add_argument('--frames',nargs='+',type=int,default=[310,325,340]);p.add_argument('--pole-search',action='store_true');p.add_argument('--fixed-forward',type=float);p.add_argument('--fixed-up',type=float);p.add_argument('--fixed-pole-fraction',type=float);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);seedfolder=Path(a.seeds).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
with np.load(seedfolder/'hand_seeds.npz') as z:seeds={k:z[k] for k in z.files}
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/sleeve_stable/Cynical_Cloth_15s.blend';bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False);scene=bpy.context.scene;arm=bpy.data.objects['达妮娅_arm'];body=bpy.data.objects['达妮娅_mesh'];original=arm.animation_data.action;original.use_fake_user=True;new=original.copy();new.name='Contact_Grouped_StaticKeyposes';new.use_fake_user=True
visibility={o:o.hide_viewport for o in bpy.data.objects if o.type=='MESH' and o!=body}
for obj in visibility:obj.hide_viewport=True
regions=skin_regions(body,arm);add_glove_hands(regions,body,arm,bpy.data.objects['Cloth']);glove=regions['extra_objects'][0];solver=ArmContactProjector(body,arm,regions,.002,limit_degrees=55,preserve_hand_orientation=True)
compiled={}
for key,faces in regions['faces'].items():
    if key=='excluded' or not faces:continue
    fs=np.asarray(faces);ids=np.unique(fs);mapping={int(v):i for i,v in enumerate(ids)};compiled[key]=(ids,np.array([[mapping[int(v)] for v in f] for f in fs]))
def audit(co,first=True):
    trees={k:BVHTree.FromPolygons(co[ids].tolist(),fs.tolist(),all_triangles=True) for k,(ids,fs) in compiled.items()};rows=[]
    for a,b in PAIRS:
        if a not in trees or b not in trees:continue
        count=0;fa=np.asarray(regions['faces'][a]);fb=np.asarray(regions['faces'][b])
        for i,j in trees[a].overlap(trees[b]):
            if triangle_crosses([Vector(v) for v in co[fa[i]]],[Vector(v) for v in co[fb[j]]]):
                count+=1
                if first:break
        rows.append({'pair':[a,b],'triangle_crossings':count})
    return {'pairs':rows,'crossing_pairs':sum(r['triangle_crossings']>0 for r in rows),'triangle_crossings':sum(r['triangle_crossings'] for r in rows)}
protected_names=['頭','首','上半身','上半身2','上半身3','下半身','足ＩＫ.L','足ＩＫ.R','足首D.L','足首D.R'];protected_names=[n for n in protected_names if n in arm.pose.bones];finger_names=[b.name for b in arm.pose.bones if b.name.startswith(HAND_PREFIX[1:])];report={'status':'STATIC_KEYPOSE_SEARCH_NOT_FULL_MOTION','source':str(source),'original_action':original.name,'frames':{},'finger_channels_changed':False,'cloth_rebaked':False,'gesture_accepted':False,'continuous_collision_detection':False};solutions=[];start=time.perf_counter();previous_quaternions=None
for frame in a.frames:
    arm.animation_data.action=original;scene.frame_set(frame);bpy.context.view_layer.update();solver.capture();base_wrist=np.array([arm.matrix_world@arm.pose.bones['手首.'+s].matrix for s in ('L','R')]);protected=np.array([arm.pose.bones[n].matrix for n in protected_names]);fingers=np.array([arm.pose.bones[n].matrix_basis for n in finger_names]);before=audit(all_coords(body,regions),False);delta=seeds['relative_translation'][list(seeds['frames']).index(frame)];upper=arm.pose.bones['上半身3'];axes=(arm.matrix_world@upper.matrix@upper.bone.matrix_local.inverted()).to_3x3();front=np.array((axes@Vector((0,-1,0))).normalized());up=np.array((axes@Vector((0,0,1))).normalized());best=None;attempts=[]
    for distance in ((a.fixed_forward,) if a.fixed_forward is not None else (0.,.025,.05,.075,.10,.125)):
        for vertical in ((a.fixed_up,) if a.fixed_up is not None else (0.,-.02,.02)):
            common=front*distance+up*vertical;shifts=np.array([common+delta*.5,common-delta*.5]);solver.apply(np.zeros(18));anchors=[[(arm.matrix_world@solver.bones[i+j].head).copy() for j in range(3)] for i in (0,3)];lateral=np.array((axes@Vector((1,0,0))).normalized());centre=np.array(arm.matrix_world@upper.head);outward_angles=[]
            for (s,e,w),shift in zip(anchors,shifts):
                axis=np.array(w-s)+shift;axis/=np.linalg.norm(axis);pole=np.array(e-s);pole-=axis*np.dot(axis,pole);pole/=np.linalg.norm(pole);outside=lateral*np.sign(np.dot(np.array(s)-centre,lateral));outside-=axis*np.dot(axis,outside);outside/=np.linalg.norm(outside);outward_angles.append(float(np.arctan2(np.dot(axis,np.cross(pole,outside)),np.dot(pole,outside))))
            for fraction in ((a.fixed_pole_fraction,) if a.fixed_pole_fraction is not None else (0.,.25,.5,.75,1.) if a.pole_search else (0.,)):
                poles=np.array(outward_angles)*fraction;x=solver.hand_translation_seed(shifts,pole_angles=poles);solver.apply(x);actual=np.array([arm.matrix_world@arm.pose.bones['手首.'+s].matrix for s in ('L','R')]);error=float(np.linalg.norm(actual[:,:3,3]-base_wrist[:,:3,3]-shifts,axis=1).max());angle=float(np.linalg.norm(x.reshape(6,3),axis=1).max()*180/np.pi);check=audit(all_coords(body,regions));item={'common_translation_m':common.tolist(),'pole_angles_rad':poles.tolist(),'wrist_target_error_m':error,'max_control_change_deg':angle,'crossing_pairs':check['crossing_pairs']};attempts.append(item)
                score=(check['crossing_pairs'],error>.001,angle>55,float(np.linalg.norm(common))+.01*fraction)
                if best is None or score<best[0]:best=(score,x.copy(),shifts.copy(),item)
                if check['crossing_pairs']==0 and error<.001 and angle<55:break
            if best[0][:3]==(0,False,False):break
        if best[0][:3]==(0,False,False):break
    solver.apply(best[1]);after=audit(all_coords(body,regions),False);actual=np.array([arm.matrix_world@arm.pose.bones['手首.'+s].matrix for s in ('L','R')]);rel=np.linalg.inv(actual[0])@actual[1];expected=base_wrist.copy();expected[:,:3,3]+=best[2];target_rel=np.linalg.inv(expected[0])@expected[1];rotation_error=max(float(actual[i,:3,:3].__sub__(base_wrist[i,:3,:3]).__abs__().max()) for i in range(2));protected_error=float(np.abs(np.array([arm.pose.bones[n].matrix for n in protected_names])-protected).max());finger_error=float(np.abs(np.array([arm.pose.bones[n].matrix_basis for n in finger_names])-fingers).max());hand_co=evaluated_coords(glove);source_index=list(seeds['source_frames']).index(frame);expected_co=seeds['source_vertices'][source_index].copy();expected_co[seeds['ids_L']]+=best[2][0];expected_co[seeds['ids_R']]+=best[2][1];surface_error=float(np.linalg.norm(hand_co-expected_co,axis=1).max());nearest=float('inf');right_faces=seeds['faces_R'];tree=BVHTree.FromPolygons(hand_co.tolist(),right_faces.tolist(),all_triangles=True)
    for v in hand_co[seeds['ids_L']]:
        q,n,i,dist=tree.find_nearest(Vector(v));nearest=min(nearest,dist)
    contact_side_ok=float(np.dot(actual[0,:3,3]-actual[1,:3,3],base_wrist[0,:3,2]))<-.003
    passed=after['triangle_crossings']==0 and contact_side_ok and best[3]['wrist_target_error_m']<.001 and best[3]['max_control_change_deg']<55 and protected_error<1e-6 and finger_error<1e-6 and rotation_error<1e-5 and nearest<.004
    row={'status':'STATIC_GEOMETRY_AND_CONTACT_PASS_REQUIRES_GESTURE_REVIEW' if passed else 'STATIC_POSE_NOT_ACCEPTED','declared_contact_side_pass':contact_side_ok,'before':before,'after':after,'selected':best[3],'relative_wrist_position_error_m':float(np.linalg.norm(rel[:3,3]-target_rel[:3,3])),'hand_rotation_matrix_max_error':rotation_error,'protected_pose_matrix_max_error':protected_error,'finger_local_matrix_max_error':finger_error,'actual_hand_vs_rigid_target_max_error_m':surface_error,'nearest_hand_vertex_surface_gap_m':nearest,'attempts':attempts};report['frames'][str(frame)]=row;solutions.append({'frame':frame,'offsets':best[1].tolist()});rotations=[b.rotation_quaternion.copy() for b in solver.bones];arm.animation_data.action=new
    for i,(b,q) in enumerate(zip(solver.bones,rotations)):
        if previous_quaternions is not None and q.dot(previous_quaternions[i])<0:q.negate()
        b.rotation_quaternion=q;b.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=b.name)
    previous_quaternions=[q.copy() for q in rotations]
    print('MMD_GROUPED_KEYPOSE',frame,json.dumps({k:v for k,v in row.items() if k!='attempts'}),flush=True);(out/'keypose_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
arm.animation_data.action=new
paths={b.path_from_id('rotation_quaternion') for b in solver.bones}
for layer in new.layers:
    for strip in layer.strips:
        for bag in strip.channelbags:
            for curve in bag.fcurves:
                if curve.data_path in paths:
                    for key in curve.keyframe_points:
                        if min(a.frames)<=key.co.x<=max(a.frames):key.interpolation='LINEAR'
for obj,value in visibility.items():obj.hide_viewport=value
for obj in regions['extra_objects']:bpy.data.objects.remove(obj,do_unlink=True)
for name in ('ClothShapePreservingTarget','ClothSimulationSurface','ClothUnskinnedVisualCarrier'):
    obj=bpy.data.objects.get(name)
    if obj:obj.hide_render=True;obj.hide_set(True)
for obj in bpy.data.objects:
    for mod in obj.modifiers:
        if mod.type in {'CLOTH','MESH_CACHE'} or (obj.name=='Cloth' and mod.type=='NODES' and 'absolute' in mod.name.lower()):mod.show_viewport=False;mod.show_render=False
report.update(seconds=time.perf_counter()-start,all_static_geometry_pass=all(r['status'].startswith('STATIC_GEOMETRY_AND_CONTACT_PASS') for r in report['frames'].values()));(out/'keypose_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');(out/'offsets.json').write_text(json.dumps(solutions),encoding='utf-8');scene['contact_motion_status']='STATIC_KEYPOSES_ONLY_UNACCEPTED_ANIMATION_CLOTH_CACHE_INVALID';scene.frame_set(a.frames[0]);bpy.ops.wm.save_as_mainfile(filepath=str(out/'MMD_Contact_Keyposes.blend'),compress=True)
