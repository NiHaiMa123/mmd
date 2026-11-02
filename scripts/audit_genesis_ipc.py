"""Independent actual-body surface audit and controlled coupling comparison."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--physics-joint-output',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve()

def cross_count(co1,faces1,co2,faces2,self_pair=False):
    b1=BVHTree.FromPolygons(co1.tolist(),faces1.tolist(),all_triangles=True)
    b2=b1 if self_pair else BVHTree.FromPolygons(co2.tolist(),faces2.tolist(),all_triangles=True)
    count=0
    for i,j in b1.overlap(b2):
        if self_pair and (i>=j or set(faces1[i])&set(faces2[j])):continue
        if triangle_crosses([Vector(v) for v in co1[faces1[i]]],[Vector(v) for v in co2[faces2[j]]]):count+=1
    return count

runs={};states={};summary={'status':'NOT_YET_ACCEPTED','scope':'Numerical hinge and cloth surfaces at recorded samples; no MMD, semantic or general continuous guarantee','pose_source':'physics_joint_output' if a.physics_joint_output else 'raw_genesis','modes':{}}
for mode in ('free','one_way','two_way'):
    directory=folder/mode
    if not (directory/'trajectory.npz').exists():continue
    state=json.loads((directory/'report.json').read_text(encoding='utf-8'))
    if state['status']!='NUMERICAL_RUN_COMPLETE_REQUIRES_CONTACT_AUDIT':continue
    trusted_native=state.get('native_state_source')=='AffineBodyStateAccessorFeature'
    with np.load(directory/('joint_output.npz' if a.physics_joint_output else 'trajectory.npz')) as archive:data={k:archive[k] for k in archive.files}
    pose=data['output_arm'] if a.physics_joint_output else data['arm']
    layers=sorted(k for k in data if k.startswith('cloth_') and k.split('_')[-1].isdigit() and len(k.split('_'))==2)
    rows=[]
    for f in range(len(data['q_rad'])):
        body=sum(cross_count(pose[f],data['arm_faces'],data[k][f],data['cloth_faces_'+k.split('_')[-1]]) for k in layers)
        own=sum(cross_count(data[k][f],data['cloth_faces_'+k.split('_')[-1]],data[k][f],data['cloth_faces_'+k.split('_')[-1]],True) for k in layers)
        between=sum(cross_count(data[left][f],data['cloth_faces_'+left.split('_')[-1]],data[right][f],data['cloth_faces_'+right.split('_')[-1]]) for i,left in enumerate(layers) for right in layers[i+1:])
        native=sum(cross_count(data['ipc_arm'][f],data['ipc_arm_faces'],data[k][f],data['cloth_faces_'+k.split('_')[-1]]) for k in layers) if 'ipc_arm' in data and trusted_native else None
        rows.append({'frame':f,'body_cloth_crossings':body,'cloth_self_crossings':own,'cloth_layers_crossings':between,'native_proxy_cloth_crossings':native})
    result={'samples':len(rows),'body_cloth_crossing_samples':sum(r['body_cloth_crossings']>0 for r in rows),'cloth_self_crossing_samples':sum(r['cloth_self_crossings']>0 for r in rows),'cloth_layer_crossing_samples':sum(r['cloth_layers_crossings']>0 for r in rows),'max_feedback_torque_nm':float(np.linalg.norm(data['feedback_torque_nm'],axis=1).max()),'rows':rows}
    result['max_fixed_pin_error_m']=max((float(np.max(np.linalg.norm(data[k][:,data['cloth_pins_'+k.split('_')[-1]]]-data[k][0,data['cloth_pins_'+k.split('_')[-1]]],axis=-1))) for k in layers if len(data['cloth_pins_'+k.split('_')[-1]])),default=0.)
    if 'ipc_arm' in data and trusted_native:
        surface_ids=np.unique(data['ipc_arm_faces']);deviation=[];depth=[]
        for f,box in enumerate(pose):
            basis=np.stack((box[4]-box[0],box[2]-box[0],box[1]-box[0]),axis=1);lengths=np.linalg.norm(basis,axis=0)
            points=(data['ipc_arm'][f,surface_ids]-box[0])@np.linalg.inv(basis).T
            outside=np.maximum(np.maximum(-points,points-1),0)*lengths
            is_outside=np.any(outside>0,axis=1);distance=np.linalg.norm(outside,axis=1)
            distance[~is_outside]=np.min(np.minimum(points[~is_outside],1-points[~is_outside])*lengths,axis=1)
            deviation.append(float(distance.max()))
            for k in layers:
                inside=(data[k][f]-box[0])@np.linalg.inv(basis).T;selected=np.all((inside>=0)&(inside<=1),axis=1)
                if selected.any():depth.append(float(np.min(np.minimum(inside[selected],1-inside[selected])*lengths,axis=1).max()))
        result.update(native_proxy_cloth_crossing_samples=sum((r['native_proxy_cloth_crossings'] or 0)>0 for r in rows),native_vs_actual_box_surface_max_deviation_m=max(deviation),native_vs_actual_box_rest_deviation_m=deviation[0],cloth_vertex_inside_actual_box_max_depth_m=max(depth,default=0.))
    (directory/('joint_output_surface_audit.json' if a.physics_joint_output else 'surface_audit.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    summary['modes'][mode]={k:v for k,v in result.items() if k!='rows'};runs[mode]=data;states[mode]=state
if set(runs)=={'free','one_way','two_way'}:
    for data in runs.values():np.testing.assert_allclose(data['target_rad'],runs['free']['target_rad'])
    one_delta=float(np.max(np.abs(runs['one_way']['q_rad']-runs['free']['q_rad'])))
    two_delta=float(np.max(np.abs(runs['two_way']['q_rad']-runs['free']['q_rad'])))
    changed=float(np.max(np.abs(runs['two_way']['q_rad']-runs['one_way']['q_rad'])))
    target_torque=summary['modes']['two_way']['max_feedback_torque_nm']
    summary['comparison']={'same_target_track':True,'one_way_vs_free_max_q_delta_rad':one_delta,'two_way_vs_free_max_q_delta_rad':two_delta,'two_way_vs_one_way_max_q_delta_rad':changed,'mechanical_feedback_observed':bool(one_delta<.005 and changed>.01 and target_torque>1e-4)}
    clean=all(summary['modes']['two_way'][key]==0 for key in ('body_cloth_crossing_samples','cloth_self_crossing_samples','cloth_layer_crossing_samples')) and summary['modes']['two_way']['max_fixed_pin_error_m']<1e-6
    summary['status']='PROBE_FEEDBACK_AND_SAMPLED_SURFACES_PASS' if clean and summary['comparison']['mechanical_feedback_observed'] else 'PROBE_NOT_ACCEPTED'
elif set(runs)=={'free','two_way'} and states['two_way'].get('feedback_mechanism')=='joint_state':
    np.testing.assert_allclose(runs['free']['target_rad'],runs['two_way']['target_rad'])
    key='output_q_rad' if a.physics_joint_output else 'q_rad'
    delta=float(np.max(np.abs(runs['two_way'][key]-runs['free'][key])))
    clean=all(summary['modes']['two_way'][key]==0 for key in ('body_cloth_crossing_samples','cloth_self_crossing_samples','cloth_layer_crossing_samples')) and summary['modes']['two_way']['max_fixed_pin_error_m']<1e-6
    summary['comparison']={'same_target_track':True,'feedback_mechanism':'joint_state','loaded_vs_unloaded_max_q_delta_rad':delta,'mechanical_feedback_observed':delta>.01}
    summary['status']='PROBE_JOINT_FEEDBACK_AND_SAMPLED_SURFACES_PASS' if clean and delta>.01 else 'PROBE_NOT_ACCEPTED'
if a.physics_joint_output:
    summary['raw_genesis_live_pose_accepted']=False
    summary['scope']+='; exported rotation-only hinge pose reconstructed from native state; internal live pose mismatch remains'
    if summary['status']=='PROBE_JOINT_FEEDBACK_AND_SAMPLED_SURFACES_PASS':summary['status']='PHYSICS_JOINT_OUTPUT_SAMPLED_PASS_LIVE_POSE_MISMATCH'
(folder/('comparison_physics_output.json' if a.physics_joint_output else 'comparison.json')).write_text(json.dumps(summary,indent=2),encoding='utf-8');print('GENESIS_CONTACT_COMPARISON',json.dumps(summary),flush=True)
