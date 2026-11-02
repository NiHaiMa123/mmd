"""Temporally coupled IK-goal feedback around a conservative anchored clump.

The optimization variables are low-frequency Cartesian offsets, elbow swivel
and forearm roll. No per-frame rotation correction is left in the output.
Discrete surface checks, source preservation and hair re-simulation are still
required; this is not a complete continuous-collision animation solver.
"""
import json,time
from pathlib import Path
import bpy,numpy as np
from mathutils import Quaternion,Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .surface import coords,audit_frame
from .projector import FrameProjector
from .root_envelope_feedback import cubic_basis
from .two_bone_contact_path import apply_two_bone_goal,clamp_reachable_goal
from .hair_position_cache import bind_position_cache
from .hair_track import add_layer
from .track import fcurves
from .linear_skin_playback import LinearSkinPlayback


def solve_spline_clump(mesh,arm,profile,bundle,initial_points,out,first,last,
                       vector,swivel=.35,ramp=3.,centres=None,width=None,
                       iterations=36,verification_step=.0625,initial_coefficients=None,parameter_scale=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise ValueError('Use a new spline output directory')
    if len(profile['control_chains'])!=1 or arm.animation_data.action is not None:raise ValueError('One explicit arm and preserved source NLA required')
    if any(w['start']<=last and w['end']>=first for w in profile.get('protected_windows',[])):raise ValueError('Spline support overlaps a protected interaction')
    source=bpy.data.filepath;scene=bpy.context.scene;chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];aux=[arm.pose.bones[n] for n in profile.get('auxiliary_twist_bones',[])];controls=bones+aux;scene.frame_set(1);bpy.context.view_layer.update();neutral=[(b.rotation_quaternion.copy(),b.location.copy(),b.scale.copy()) for b in controls];head0=np.array(arm.matrix_world@arm.pose.bones[bundle['anchor_bone']].matrix);centres=np.asarray(centres if centres is not None else np.linspace(first+1,last-1,5));width=float(np.median(np.diff(centres))) if width is None else float(width);vector=np.asarray(vector,dtype=float);scale=np.array([.05,.05,.05,.2,.25,.25,.3,.3] if parameter_scale is None else parameter_scale,dtype=float);dimension=len(scale);coefficients=np.zeros((len(centres),dimension)) if initial_coefficients is None else np.asarray(initial_coefficients,dtype=float);
    if len(centres)<2 or np.any(np.diff(centres)<=0) or not np.isfinite(width) or ramp<=0 or int(first)!=first or int(last)!=last:raise ValueError('Ordered spline centres, positive widths and integer frame endpoints required')
    if profile.get('units_to_m',1.)!=1. or first>=last or verification_step<=0 or width<=0 or scale.shape!=(8,) or not np.all(np.isfinite(scale)) or np.min(scale)<=0:raise ValueError('Metre coordinates, valid time support and positive finite parameter scales required')
    if abs((last-first)/verification_step-round((last-first)/verification_step))>1e-6:raise ValueError('Verification step must divide the output interval')
    if coefficients.shape!=(len(centres),dimension):raise ValueError('Initial coefficients must match the chosen centres and eight parameters')
    frames=np.arange(first,last+.00001,verification_step);rows=[];start=time.monotonic()
    def fade(frame):
        u=np.clip((frame-first)/ramp,0,1);v=np.clip((last-frame)/ramp,0,1)
        return float(u*u*(3-2*u)*v*v*(3-2*v))
    skin=None;skin_info=dict(enabled=False)
    try:
        body_ids=np.array(sorted({i for role,ids in bundle['parts']['ids'].items() if not role.startswith('hair') for i in ids}))
        if set(body_ids.tolist())&set(bundle['ids'].tolist()):raise ValueError('Shared skin/hair vertices need native evaluation')
        skin=LinearSkinPlayback(mesh,arm,body_ids);skin.modifier.show_viewport=False;bpy.context.view_layer.update()
    except ValueError as error:skin_info['reason']=str(error)
    for frame in frames:
        for b,(q,loc,size) in zip(controls,neutral):b.rotation_quaternion=q;b.location=loc;b.scale=size
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();s=np.array(arm.matrix_world@bones[0].head);e=np.array(arm.matrix_world@bones[1].head);w=np.array(arm.matrix_world@bones[2].head);head=np.array(arm.matrix_world@arm.pose.bones[bundle['anchor_bone']].matrix)
        rows.append(dict(frame=float(frame),q=[b.rotation_quaternion.copy() for b in controls],loc=[b.location.copy() for b in controls],size=[b.scale.copy() for b in controls],wrist=w,shoulder=s,lengths=(np.linalg.norm(e-s),np.linalg.norm(w-e)),head=head,fade=fade(frame),basis=cubic_basis(frame,centres,width)*fade(frame),skin_rest=None if skin is None else skin.capture_rest(coords(mesh))))
    if skin:skin.modifier.show_viewport=skin.old_enabled;bpy.context.view_layer.update()
    selected=[rows[0],rows[-1]];hair=[]
    for row in selected:
        delta=row['head']@np.linalg.inv(head0);hair.append(np.asarray(initial_points)@delta[:3,:3].T+delta[:3,3])
    obstacle=bind_position_cache(mesh,bundle['ids'],hair,out/'ConservativeClump.pc2',first=first,anchor_armature=arm,anchor_bone=bundle['anchor_bone'],anchor_matrices=[r['head'] for r in selected],sample_step=last-first);obstacle_mod=mesh.modifiers[-1];moving=[role for role,ns in profile['bone_roles'].items() if role.startswith(('arm','hand')) and any(n in ns for n in chain)];cp=dict(profile,pairs=profile['pairs']+[[role,'hair_mobile'] for role in moving],extra_contact_targets=['hair_mobile'],preserve_wrist_orientation=False,clearance_m=.002);projector=FrameProjector(mesh,arm,cp,bundle['parts'],[chain]);forearm=[b for b in aux if bones[1] in b.parent_recursive and b in bones[2].parent_recursive];roll_bone=forearm[0] if forearm else None;upper_roll=[b for b in aux if b not in forearm];upper_roll=upper_roll[0] if upper_roll else None
    def apply(row,coeff):
        frame=row['frame'];scene.frame_set(int(frame),subframe=frame%1)
        for b,q,loc,size in zip(controls,row['q'],row['loc'],row['size']):b.rotation_quaternion=q;b.location=loc;b.scale=size
        arm.update_tag();bpy.context.view_layer.update();heading=(arm.matrix_world@bones[2].matrix).to_quaternion();parameters=(row['basis']@coeff)*scale
        if row['fade']>0:
            goal=row['wrist']+row['fade']*vector+parameters[:3];goal,_=clamp_reachable_goal(row['shoulder'],row['lengths'],goal)
            if upper_roll:upper_roll.rotation_quaternion=row['q'][controls.index(upper_roll)]@Quaternion((0,1,0),float(parameters[7]));arm.update_tag();bpy.context.view_layer.update()
            apply_two_bone_goal(arm,chain,goal,1.,row['fade']*swivel+parameters[3])
            bones[0].rotation_quaternion=bones[0].rotation_quaternion@Quaternion((0,1,0),float(parameters[4]));arm.update_tag();bpy.context.view_layer.update()
            def restore_endpoint():
                pivot=arm.matrix_world@bones[1].head;current=arm.matrix_world@bones[2].head-pivot;desired=type(pivot)(goal)-pivot
                if current.length<1e-8 or desired.length<1e-8:raise ValueError('Invalid forearm endpoint')
                rotation=current.rotation_difference(desired);world=Matrix.Translation(pivot)@rotation.to_matrix().to_4x4()@Matrix.Translation(-pivot)@(arm.matrix_world@bones[1].matrix);bones[1].matrix=arm.matrix_world.inverted()@world;bones[1].location=row['loc'][1];bones[1].scale=row['size'][1];arm.update_tag();bpy.context.view_layer.update()
            restore_endpoint();bones[1].rotation_quaternion=bones[1].rotation_quaternion@Quaternion((0,1,0),float(parameters[5]));arm.update_tag();bpy.context.view_layer.update();restore_endpoint()
            if roll_bone:roll_bone.rotation_quaternion=row['q'][controls.index(roll_bone)]@Quaternion((0,1,0),float(parameters[6]));arm.update_tag();bpy.context.view_layer.update();restore_endpoint()
            world=heading.to_matrix().to_4x4();world.translation=arm.matrix_world@bones[2].head;bones[2].matrix=arm.matrix_world.inverted()@world
            for b,loc,size in zip(controls,row['loc'],row['size']):b.location=loc;b.scale=size
            arm.update_tag();bpy.context.view_layer.update()
        if skin and skin.active:
            co=np.zeros((len(mesh.data.vertices),3));co[skin.ids]=skin.forward(row['skin_rest']);delta=row['head']@np.linalg.inv(head0);co[bundle['ids']]=np.asarray(initial_points)@delta[:3,:3].T+delta[:3,3];return co
        return coords(mesh)
    if skin:
        skin.hide();errors=[]
        for index in (0,len(rows)//2,len(rows)-1):
            row=rows[index];predicted=apply(row,coefficients);mesh.hide_viewport=False;bpy.context.view_layer.update();actual=coords(mesh);errors.append(float(np.max(np.linalg.norm(predicted[skin.ids]-actual[skin.ids],axis=1))));mesh.hide_viewport=True;bpy.context.view_layer.update()
        error=max(errors);skin_info=dict(enabled=error<1e-5,max_forward_error_m=error,body_vertices=len(skin.ids),pose_matrices=len(skin.names))
        if error>=1e-5:skin.restore()
        print('SPLINE_SKIN_ACCELERATOR',json.dumps(skin_info),flush=True)
    def audit(row,coeff,witness=False):
        co=apply(row,coeff);report=audit_frame(mesh,arm,cp,bundle['parts'],hair=False,cap=1000000,coordinates_m=co,return_witness_pairs=witness);return co,report
    head_ids=np.asarray(bundle['parts']['ids']['head']);head_set=set(head_ids.tolist());head_lookup={int(v):i for i,v in enumerate(head_ids)};head_faces=np.array([[head_lookup[i] for i in f] for f in bundle['parts']['faces']['head']]);head_banks={};head_trees={};bary_basis=[Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))]
    def head_guards(index,co,new_constraints):
        bank=head_banks.setdefault(index,{})
        for constraint in new_constraints:
            im,wm,it,wt,normal,gap=constraint
            if all(i in head_set for i in it):bank[(tuple(im),tuple(np.round(wm,3)))]=(list(im),list(wm))
        if not bank:return []
        if index not in head_trees:head_trees[index]=BVHTree.FromPolygons(co[head_ids].tolist(),head_faces.tolist(),all_triangles=True)
        result=[];tree=head_trees[index]
        for im,wm in bank.values():
            point=Vector(np.asarray(wm)@co[im]);q,n,face,d=tree.find_nearest(point)
            if q is None:continue
            gap=float((point-q).dot(n))
            if d>.03 and gap>=0:continue
            if d>1e-6 and abs(gap)/d<.5:continue
            target=head_ids[head_faces[face]];weights=barycentric_transform(q,*[Vector(co[i]) for i in target],*bary_basis);result.append((im,wm,target.tolist(),list(weights),np.array(n),gap))
        result.sort(key=lambda c:c[-1]);return result[:256]
    second=np.diff(np.eye(len(centres)),n=2,axis=0);regularizer=np.eye(coefficients.size)*.000005+np.kron(second.T@second,np.eye(dimension))*.00002;active={k for k in range(len(rows)) if abs((rows[k]['frame']-first)*4-round((rows[k]['frame']-first)*4))<1e-7};history=[];dense_reports=None
    for iteration in range(iterations):
        blocks=[];right=[];sets=[];failed=[]
        for k in sorted(active):
            row=rows[k];co,report=audit(row,coefficients,True)
            bad=report['ordinary_crossings'] or report['ordinary_contained_samples']
            if bad:failed.append(row['frame'])
            cs=projector.constraints(report,co) if bad else []
            head_rows=[dict(p,moving_vertices=[],target_vertices=[]) for p in report['pairs'] if p['pair'][1]=='head' and p['triangle_crossings']]
            head_witness=projector.constraints(dict(pairs=head_rows),co) if head_rows else []
            guards=head_guards(k,co,cs+head_witness)
            cs=[c for c in cs if not all(i in head_set for i in c[2])]+guards
            if not cs:continue
            feature=projector.features(co,cs);normal=np.array([c[-2] for c in cs]);gap=np.array([c[-1] for c in cs]);local=np.zeros((len(cs),dimension));parameters=row['basis']@coefficients
            # Perturb one local goal parameter by changing a temporary spline
            # coefficient with nonzero support at this sample.
            anchor=int(np.argmax(row['basis']));basis=row['basis'][anchor]
            if basis<1e-8:continue
            for j in range(dimension):
                perturbed=coefficients.copy();perturbed[anchor,j]+=.01/basis;new=apply(row,perturbed);local[:,j]=np.einsum('ij,ij->i',projector.features(new,cs)-feature,normal)/.01
            blocks.append(np.hstack([local*b for b in row['basis']]));right.append(cp['clearance_m']-gap);sets.append((row,cs,feature,normal,gap))
        print('SPLINE_CLUMP_ITER',iteration,len(failed),len(sets),flush=True)
        maximum_deficit=max((float(np.max(r)) for r in right),default=0.)
        if not failed and maximum_deficit<.0001:
            dense_reports=[];misses=[]
            for k,row in enumerate(rows):
                co,report=audit(row,coefficients);bad=report['ordinary_crossings'] or report['ordinary_contained_samples'];dense_reports.append(dict(frame=row['frame'],crossings=report['ordinary_crossings'],contained=report['ordinary_contained_samples']))
                if bad:misses.append(k)
            if not misses:break
            active.update(misses);history.append(dict(iteration=iteration,dense_failures=len(misses),added_times=[rows[k]['frame'] for k in misses]));continue
        if not blocks:break
        J=np.vstack(blocks);rhs=np.concatenate(right);linear_active=rhs>0
        for guard_iteration in range(6):
            A=J[linear_active];b=rhs[linear_active];step=np.linalg.solve(A.T@A+regularizer,A.T@b-regularizer@coefficients.ravel()).reshape(coefficients.shape);largest=np.max(np.abs(step))
            if largest>.35:step*=.35/largest
            predicted=rhs-J@step.ravel();added=(predicted>1e-8)&~linear_active
            if not np.any(added):break
            linear_active|=added
        old=float(np.maximum(rhs,0)@np.maximum(rhs,0)+coefficients.ravel()@regularizer@coefficients.ravel());accepted=False
        for factor in (1.,.5,.25,.1):
            candidate=np.clip(coefficients+factor*step,-2.,2.);score=float(candidate.ravel()@regularizer@candidate.ravel())
            for row,cs,feature,normal,gap in sets:
                new=apply(row,candidate);change=np.einsum('ij,ij->i',projector.features(new,cs)-feature,normal);deficit=np.maximum(cp['clearance_m']-gap-change,0);score+=float(deficit@deficit)
            if score<old-1e-12:coefficients=candidate;accepted=True;break
        history.append(dict(iteration=iteration,failed_times=failed,accepted=accepted,objective=old));(out/'progress.json').write_text(json.dumps(dict(history=history,coefficients=coefficients.tolist(),parameter_scale=scale.tolist(),centres=centres.tolist(),basis_width=width,frame_range=[first,last]),ensure_ascii=False,indent=2),encoding='utf8')
        if not accepted:break
    if skin:skin.restore()
    poses=[];checks=[];wrist_points=[];source_points=[]
    for row in rows:
        co,report=audit(row,coefficients);poses.append([b.rotation_quaternion.copy() for b in controls]);wrist_points.append(np.array(arm.matrix_world@bones[2].head));source_points.append(row['wrist']);checks.append(dict(frame=row['frame'],crossings=report['ordinary_crossings'],contained=report['ordinary_contained_samples'],pairs=[(p['pair'],p['triangle_crossings']) for p in report['pairs'] if p['triangle_crossings']]))
    mesh.modifiers.remove(obstacle_mod);mesh.data.attributes.remove(mesh.data.attributes[obstacle['selection_attribute']]);action=bpy.data.actions.new('Contact_TemporallyCoupledClumpIK');action.use_fake_user=True;ad=arm.animation_data;ad.action=action;previous={}
    for row,qs in zip(rows,poses):
        for b,q in zip(controls,qs):
            if b.name in previous and q.dot(previous[b.name])<0:q.negate()
            previous[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=row['frame'],group=b.name)
    for c in fcurves(action):
        for key in c.keyframe_points:key.interpolation='LINEAR'
    ad.action=None;strip=add_layer(arm,action,'Temporally coupled clump feedback','REPLACE',first,last);strip.extrapolation='NOTHING';scene.frame_set(int((first+last)/2));candidate=out/'Body_SplineClumpFeedback_Candidate.blend';bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True);wrist_points=np.array(wrist_points);source_points=np.array(source_points);np.savez_compressed(out/'trajectory.npz',frames=frames,wrist=wrist_points,source_wrist=source_points);result=dict(status='TIME_SPLINE_CLUMP_REQUIRES_INDEPENDENT_VALIDATION',accepted=False,source=source,candidate=str(candidate),frames=[first,last],sample_step=verification_step,sample_count=len(checks),failed_samples=sum(bool(x['crossings'] or x['contained']) for x in checks),samples=checks,skin_acceleration=skin_info,parameter_scale=scale.tolist(),parameter_names=['wrist_x','wrist_y','wrist_z','elbow_swivel','upper_material_roll','forearm_material_roll','forearm_aux_roll','upper_aux_roll'],coefficients=coefficients.tolist(),centres=centres.tolist(),width=width,base_vector=vector.tolist(),base_swivel=swivel,history=history,max_wrist_offset_m=float(np.linalg.norm(wrist_points-source_points,axis=1).max()),peak_source_wrist_speed_m_per_frame=float(np.linalg.norm(np.diff(source_points,axis=0),axis=1).max()/verification_step),peak_repaired_wrist_speed_m_per_frame=float(np.linalg.norm(np.diff(wrist_points,axis=0),axis=1).max()/verification_step),original_actions_edited=False,hair_resimulation_required=True,all_hair_solved=False,seconds=time.monotonic()-start);(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
