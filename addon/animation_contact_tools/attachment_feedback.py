"""Temporally coupled, bounded arm rotations around actual fixed hair roots.

This is a local contact optimizer, not a collision-free path guarantee.
Independent dense checks and hair re-simulation remain required.
"""
import json,time
from pathlib import Path
import bpy,numpy as np
from .surface import coords,audit_frame
from .projector import FrameProjector
from .root_envelope_feedback import cubic_basis
from .attachment_contact import attachment_contacts,attachment_linear_gap
from .exact_skin_collider import build_exact_skin_topology
from .hair_track import add_layer
from .track import fcurves


def solve_attachment_feedback(mesh,arm,profile,parts,envelope,out,centres,width=2.,limit_degrees=20.,iterations=32,sample_step=.5,initial_coefficients=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    if (out/'report.json').exists():raise ValueError('Choose a new attachment-feedback output directory')
    if arm.animation_data.action is not None or len(profile['control_chains'])!=1:raise ValueError('One arm and preserved NLA source required')
    first,last=float(min(centres)-2*width),float(max(centres)+2*width)
    if any(w['start']<=last and w['end']>=first for w in profile.get('protected_windows',[])):raise ValueError('Feedback intersects protected contact')
    bp=dict(profile,preserve_wrist_orientation=False)
    solver=FrameProjector(mesh,arm,bp,parts,profile['control_chains'],limit_degrees=limit_degrees)
    skin_ids,skin_faces,meta=build_exact_skin_topology(mesh,arm,profile,triangulate=True)
    attachments=np.asarray(envelope['attachment_points']);bind=np.asarray(envelope['anchor_bind_matrix']);anchor=envelope['anchor_bone'];states=[]
    for f in np.arange(first,last+.001,sample_step):
        bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();delta=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix)@np.linalg.inv(bind)
        states.append({'frame':float(f),'base':[q.copy() for q in solver.base], 'basis':cubic_basis(f,centres,width),'points':attachments@delta[:3,:3].T+delta[:3,3]})
    coefficients=np.zeros((len(centres),solver.n)) if initial_coefficients is None else np.asarray(initial_coefficients,dtype=float)
    if coefficients.shape!=(len(centres),solver.n) or not np.all(np.isfinite(coefficients)):raise ValueError('Invalid initial trajectory coefficients')
    coefficients=np.asarray([solver.bounded(row) for row in coefficients]);history=[];clearance=float(profile['clearance_m']);body_weight=4.
    def activate(state,coeff):
        f=state['frame'];bpy.context.scene.frame_set(int(f),subframe=f%1);solver.base=state['base'];solver.wrist_base=[];solver.hand_frames=[];solver.apply(state['basis']@coeff);return coords(mesh)
    def bounded(coeff):return np.asarray([solver.bounded(row) for row in coeff])
    for iteration in range(iterations):
        blocks=[];rhs=[];sets=[];worst=1.;crossings=0
        for state in states:
            co=activate(state,coefficients);root=attachment_contacts(co,skin_ids,skin_faces,state['points'],clearance);worst=min(worst,root['minimum_distance']);audit=audit_frame(mesh,arm,bp,parts,hair=False,cap=100000);cs=solver.constraints(audit,co);crossings+=audit['ordinary_crossings'];nroot=len(root['distance'])
            if not nroot and not cs:continue
            bodybase=solver.features(co,cs).reshape(-1,3);bn=np.asarray([c[-2] for c in cs]).reshape(-1,3);bg=np.asarray([c[-1] for c in cs]);features=np.r_[root['distance'],bg];local=np.zeros((len(features),solver.n));x=state['basis']@coefficients
            for j in range(solver.n):
                pert=x.copy();pert[j]+=.001;solver.apply(pert);new=coords(mesh);local[:nroot,j]=(attachment_linear_gap(new,root)-root['distance'])/.001
                if cs:local[nroot:,j]=np.einsum('ij,ij->i',solver.features(new,cs)-bodybase,bn)/.001
            solver.apply(x);weights=np.r_[np.ones(nroot),np.full(len(bg),body_weight)];blocks.append(np.hstack([local*value for value in state['basis']])*weights[:,None]);rhs.append((clearance-features)*weights);sets.append((state,root,cs,bodybase,bn,bg))
        print('EXACT_FEEDBACK_ITER',iteration,round(worst*1000,3),crossings,len(sets),flush=True)
        if not sets:break
        J=np.vstack(blocks);b=np.concatenate(rhs);regularization=.00005
        step=np.linalg.solve(J.T@J+np.eye(J.shape[1])*regularization,J.T@b-regularization*coefficients.ravel()).reshape(coefficients.shape)
        largest=max(np.linalg.norm(row[j:j+3]) for row in step for j in range(0,solver.n,3))
        if largest>np.radians(3):step*=np.radians(3)/largest
        old=float(np.maximum(b,0)@np.maximum(b,0));accepted=False
        for factor in (1.,.5,.25,.1):
            candidate=bounded(coefficients+factor*step);score=0.
            for state,root,cs,bodybase,bn,bg in sets:
                co=activate(state,candidate);deficit=np.maximum(clearance-attachment_linear_gap(co,root),0);score+=float(deficit@deficit)
                if cs:
                    gap=bg+np.einsum('ij,ij->i',solver.features(co,cs)-bodybase,bn);d=np.maximum(clearance-gap,0);score+=float(d@d)*body_weight**2
            if score<old-1e-12:coefficients=candidate;accepted=True;break
        history.append({'iteration':iteration,'min_root_gap_m':worst,'body_crossings':crossings,'objective':old,'accepted':accepted});(out/'progress.json').write_text(json.dumps({'history':history,'coefficients':coefficients.tolist()},indent=2),encoding='utf8')
        if not accepted:break
    # Bake at quarter frames, including the exactly zero support endpoints.
    poses=[];rows=[];outside_checks={};source=bpy.data.filepath
    for f in (first-.125,last+.125,256.,285.,321.):
        bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();outside_checks[f]=coords(mesh)
    for f in np.arange(first,last+.001,.25):
        bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();solver.capture();base=[q.copy() for q in solver.base];heading=(arm.matrix_world@solver.bones[2].matrix).to_quaternion();delta=np.array(arm.matrix_world@arm.pose.bones[anchor].matrix)@np.linalg.inv(bind);points=attachments@delta[:3,:3].T+delta[:3,3];state={'frame':float(f),'base':base,'basis':cubic_basis(f,centres,width)};co=activate(state,coefficients);contact=attachment_contacts(co,skin_ids,skin_faces,points,clearance);audit=audit_frame(mesh,arm,bp,parts,hair=False,cap=100000)
        rows.append({'frame':float(f),'root_min_distance_m':contact['minimum_distance'],'body_crossings':audit['ordinary_crossings'],'body_contained_samples':audit['ordinary_contained_samples'],'heading_delta_degrees':float(np.degrees(heading.rotation_difference((arm.matrix_world@solver.bones[2].matrix).to_quaternion()).angle))});poses.append((float(f),[q.rotation_quaternion.copy() for q in solver.bones],co.copy()))
    ad=arm.animation_data;action=bpy.data.actions.new('ExactRoot_ArmAbsolute');ad.action=action;continuity={}
    for f,qs,co in poses:
        for bone,q in zip(solver.bones,qs):
            if bone.name in continuity and q.dot(continuity[bone.name])<0:q.negate()
            continuity[bone.name]=q.copy();bone.rotation_quaternion=q;bone.keyframe_insert('rotation_quaternion',frame=f,group=bone.name)
    for curve in fcurves(action):
        for key in curve.keyframe_points:key.interpolation='LINEAR'
    ad.action=None;strip=add_layer(arm,action,'Exact fixed hair root / bounded arm feedback','REPLACE',int(first),last);strip.extrapolation='NOTHING';error=0.;outside_error=0.
    for f,qs,expected in poses:
        bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();error=max(error,float(np.max(np.abs(coords(mesh)-expected))))
    for f,expected in outside_checks.items():
        bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();outside_error=max(outside_error,float(np.max(np.abs(coords(mesh)-expected))))
    result={'status':'EXACT_ATTACHMENT_CANDIDATE_NOT_YET_ACCEPTED','source':source,'frames':[first,last],'coefficients':coefficients.tolist(),'centres':list(centres),'width':width,'history':history,'quarter_samples':rows,'layer_error_m':error,'outside_phase_and_protected_error_m':outside_error,'skin_topology':meta,'root_failed_samples':sum(r['root_min_distance_m']<.0029 for r in rows),'body_failed_samples':sum(r['body_crossings'] or r['body_contained_samples'] for r in rows),'max_heading_delta_degrees':max(r['heading_delta_degrees'] for r in rows),'original_actions_edited':False,'hair_resimulation_required':True,'seconds':time.monotonic()-started}
    result['body_failed_samples']=sum(bool(r['body_crossings'] or r['body_contained_samples']) for r in rows)
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');assert error<2e-6 and outside_error<2e-6,result
    bpy.context.scene.frame_set(244);path=out/'ExactRoot_Arm_Candidate_NotAccepted.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path),compress=True);result['candidate']=str(path);(out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
