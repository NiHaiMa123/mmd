"""Bounded arm-path fallback when a simulated clump cannot retain its shape.

Searches a smooth translation family, solves length-preserving two-bone IK,
preserves wrist world orientation, and gates every candidate on actual skin
and a conservative head-transported clump. Hair must be re-simulated afterward.
"""
import json,time
from pathlib import Path
import bpy,numpy as np
from .surface import coords,audit_frame
from .two_bone_contact_path import apply_two_bone_goal,clamp_reachable_goal
from .hair_track import add_layer
from .track import fcurves
from .projector import FrameProjector
from .hair_position_cache import bind_position_cache


def solve_clump_detour(mesh,arm,profile,bundle,initial_points,out,first,last,
                       ramp=4.,amplitudes=(.025,.05,.075),sample_step=.25,
                       joint_limit_degrees=35.,swivels=(0.,-.15,.15),
                       wrist_polish_limit_degrees=3.,directions=None,refinement_iterations=24):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise ValueError('Use a fresh detour output')
    if len(profile['control_chains'])!=1 or arm.animation_data.action is not None:
        raise ValueError('One explicit arm chain and source NLA required')
    if any(w['start']<=last and w['end']>=first for w in profile.get('protected_windows',[])):
        raise ValueError('Detour overlaps a protected interaction')
    scene=bpy.context.scene;chain=profile['control_chains'][0];bones=[arm.pose.bones[n] for n in chain];aux=[arm.pose.bones[n] for n in profile.get('auxiliary_twist_bones',[])];all_bones=bones+aux;scene.frame_set(1);bpy.context.view_layer.update();head0=np.array(arm.matrix_world@arm.pose.bones[bundle['anchor_bone']].matrix);rows=[];start=time.monotonic();hair_profile=dict(profile,pairs=[])
    def fade(frame):
        u=np.clip((frame-first)/ramp,0,1);v=np.clip((last-frame)/ramp,0,1)
        return float(u*u*(3-2*u)*v*v*(3-2*v))
    for frame in np.arange(first,last+.001,sample_step):
        scene.frame_set(int(frame),subframe=frame%1);bpy.context.view_layer.update();head=np.array(arm.matrix_world@arm.pose.bones[bundle['anchor_bone']].matrix);delta=head@np.linalg.inv(head0);s=np.array(arm.matrix_world@bones[0].head);e=np.array(arm.matrix_world@bones[1].head);w=np.array(arm.matrix_world@bones[2].head)
        rows.append(dict(frame=float(frame),base=[b.rotation_quaternion.copy() for b in bones],all_base=[b.rotation_quaternion.copy() for b in all_bones],locations=[b.location.copy() for b in all_bones],scales=[b.scale.copy() for b in all_bones],wrist=w,shoulder=s,lengths=(np.linalg.norm(e-s),np.linalg.norm(w-e)),hair=np.asarray(initial_points)@delta[:3,:3].T+delta[:3,3],weight=fade(frame)))
    priority=sorted(rows,key=lambda r:(abs(r['frame']-244),r['frame']))
    heads=[]
    for row in rows:
        scene.frame_set(int(row['frame']),subframe=row['frame']%1);bpy.context.view_layer.update();heads.append(np.array(arm.matrix_world@arm.pose.bones[bundle['anchor_bone']].matrix))
    obstacle=bind_position_cache(mesh,bundle['ids'],np.array([r['hair'] for r in rows]),out/'ConservativeRestClump.pc2',first=first,anchor_armature=arm,anchor_bone=bundle['anchor_bone'],anchor_matrices=heads,sample_step=sample_step)
    obstacle_mod=mesh.modifiers[-1]
    def remove_obstacle():
        mesh.modifiers.remove(obstacle_mod);mesh.data.attributes.remove(mesh.data.attributes[obstacle['selection_attribute']]);bpy.context.view_layer.update()
    moving_roles=[role for role,names in profile['bone_roles'].items() if role.startswith(('arm','hand')) and any(n in names for n in chain)]
    joint_profile=dict(profile,preserve_wrist_orientation=True,clearance_m=.001,extra_contact_targets=['hair_mobile'],pairs=profile['pairs']+[[role,'hair_mobile'] for role in moving_roles])
    joint_polisher=FrameProjector(mesh,arm,joint_profile,bundle['parts'],[chain],limit_degrees=6.)
    polisher=FrameProjector(mesh,arm,dict(joint_profile,preserve_wrist_orientation=False),bundle['parts'],[chain],limit_degrees=wrist_polish_limit_degrees)
    polisher.bones=[bones[2]];polisher.n=3
    twist_polisher=None
    if aux:
        twist_polisher=FrameProjector(mesh,arm,joint_profile,bundle['parts'],[chain],limit_degrees=15.)
        twist_polisher.bones=aux;twist_polisher.n=3*len(aux)
        mask=np.tile([0.,1.,0.],len(aux));old_apply=twist_polisher.apply;old_bounded=twist_polisher.bounded
        twist_polisher.apply=lambda x:old_apply(np.asarray(x)*mask)
        twist_polisher.bounded=lambda x:old_bounded(np.asarray(x)*mask)
    directions=np.array([(x,y,z) for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1) if x or y or z] if directions is None else directions,dtype=float)
    if directions.ndim!=2 or directions.shape[1]!=3 or np.any(np.linalg.norm(directions,axis=1)<1e-10):raise ValueError('Nonzero 3D route directions required')
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    def activate(row,vector,swivel):
        frame=row['frame'];scene.frame_set(int(frame),subframe=frame%1)
        for b,q,loc,scale in zip(all_bones,row['all_base'],row['locations'],row['scales']):b.rotation_quaternion=q;b.location=loc;b.scale=scale
        arm.update_tag();bpy.context.view_layer.update()
        heading=(arm.matrix_world@bones[2].matrix).to_quaternion()
        if row['weight']>0:
            target,clamp=clamp_reachable_goal(row['shoulder'],row['lengths'],row['wrist']+vector*row['weight']);detail=apply_two_bone_goal(arm,chain,target,1.,swivel*row['weight'])
        else:detail=dict(endpoint_error_m=0.,goal_clamp_m=0.)
        co=coords(mesh);body=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        if twist_polisher and (body['ordinary_crossings'] or body['ordinary_contained_samples']):
            twist_polisher.capture();twist_polisher.solve(iterations=refinement_iterations);co=coords(mesh);body=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        if body['ordinary_crossings'] or body['ordinary_contained_samples']:
            joint_polisher.capture();joint_polisher.solve(iterations=refinement_iterations);co=coords(mesh);body=audit_frame(mesh,arm,profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        residual=audit_frame(mesh,arm,joint_profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        if residual['ordinary_crossings'] or residual['ordinary_contained_samples']:
            polisher.capture();polisher.solve(iterations=refinement_iterations);co=coords(mesh);body=audit_frame(mesh,arm,profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        for b,loc,scale in zip(all_bones,row['locations'],row['scales']):b.location=loc;b.scale=scale
        arm.update_tag();bpy.context.view_layer.update();co=coords(mesh);body=audit_frame(mesh,arm,profile,bundle['parts'],hair=False,cap=1000000,coordinates_m=co)
        angles=[float(np.degrees(q.rotation_difference(b.rotation_quaternion).angle)) for q,b in zip(row['base'],bones)];co[bundle['ids']]=row['hair'];hair=audit_frame(mesh,arm,hair_profile,bundle['parts'],hair=True,cap=1000000,coordinates_m=co)
        return dict(frame=frame,body_crossings=body['ordinary_crossings'],body_contained_samples=body['ordinary_contained_samples'],hair_crossings=hair['ordinary_crossings'],hair_pairs=[(r['pair'],r['triangle_crossings']) for r in hair['pairs'] if r['triangle_crossings']],body_pairs=[(r['pair'],r['triangle_crossings']) for r in body['pairs'] if r['triangle_crossings']],angles=angles,wrist_heading_error_degrees=float(np.degrees(heading.rotation_difference((arm.matrix_world@bones[2].matrix).to_quaternion()).angle)),wrist_offset_m=float(np.linalg.norm(np.array(arm.matrix_world@bones[2].head)-row['wrist'])),**detail)
    trials=[];chosen=None
    for amplitude in amplitudes:
        for direction in directions:
            for swivel in swivels:
                vector=direction*amplitude;failure=None
                for row in priority:
                    result=activate(row,vector,swivel)
                    if max(result['angles'][:2])>joint_limit_degrees or result['body_crossings'] or result['body_contained_samples'] or result['hair_crossings']:
                        failure=result;break
                trials.append(dict(vector=vector.tolist(),swivel=swivel,failure=failure))
                if len(trials)%24==0:
                    print('CLUMP_ROUTE_SEARCH',len(trials),amplitude,flush=True)
                    (out/'search_progress.json').write_text(json.dumps(dict(trials=trials),ensure_ascii=False),encoding='utf8')
                if failure is None:chosen=(vector,swivel);break
            if chosen:break
        if chosen:break
    (out/'search.json').write_text(json.dumps(dict(trials=trials),ensure_ascii=False,indent=2),encoding='utf8')
    if chosen is None:
        remove_obstacle()
        result=dict(status='NO_FEASIBLE_CLUMP_DETOUR_IN_BOUNDED_FAMILY',accepted=False,frames=[first,last],trial_count=len(trials),seconds=time.monotonic()-start)
        (out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8');return result
    vector,swivel=chosen;poses=[];checks=[]
    for row in rows:
        checks.append(activate(row,vector,swivel));poses.append((row['frame'],[b.rotation_quaternion.copy() for b in all_bones]))
    remove_obstacle()
    action=bpy.data.actions.new('Contact_ClumpDetour_Absolute');action.use_fake_user=True;ad=arm.animation_data;ad.action=action;previous={}
    for frame,quaternions in poses:
        for b,q in zip(all_bones,quaternions):
            if b.name in previous and q.dot(previous[b.name])<0:q.negate()
            previous[b.name]=q.copy();b.rotation_quaternion=q;b.keyframe_insert('rotation_quaternion',frame=frame,group=b.name)
    for c in fcurves(action):
        for key in c.keyframe_points:key.interpolation='LINEAR'
    ad.action=None;strip=add_layer(arm,action,'Conservative clump / bounded arm detour','REPLACE',first,last);strip.extrapolation='NOTHING';candidate=out/'Body_ClumpDetour_RequiresResimulation.blend';scene.frame_set(245);bpy.ops.wm.save_as_mainfile(filepath=str(candidate),compress=True);result=dict(status='BOUNDED_CLUMP_DETOUR_REQUIRES_RESIMULATION_AND_DENSE_VALIDATION',accepted=False,source=None,candidate=str(candidate),frames=[first,last],sample_step=sample_step,sample_count=len(checks),trial_count=len(trials),vector=vector.tolist(),swivel=swivel,max_wrist_offset_m=max(r['wrist_offset_m'] for r in checks),max_wrist_heading_error_degrees=max(r['wrist_heading_error_degrees'] for r in checks),max_upper_elbow_degrees=max(max(r['angles'][:2]) for r in checks),samples=checks,original_actions_edited=False,bone_length_changed=False,protected_interaction_modified=False,hair_is_conservative_obstacle_only=True,seconds=time.monotonic()-start);(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
