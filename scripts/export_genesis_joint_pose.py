"""Reconstruct the probe skeleton from the SAME native state as the cloth.

Preserve raw Genesis output. This explicit single-hinge output bridge is not
a fix for Genesis's internal state sequencing and not a general MMD retargeter.
The reconstructed bone keeps its fixed pivot and length; audit its surface
independently rather than substituting the deformable ABD collision mesh.
"""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();folder=Path(a.input).resolve()
report={'scope':'Single-hinge physical-output-to-skeleton bridge; original runtime pose retained','cases':{}}
for mode in ('free','two_way'):
    path=folder/mode
    state=json.loads((path/'report.json').read_text(encoding='utf-8'))
    if state.get('native_state_source')!='AffineBodyStateAccessorFeature':raise ValueError('An authoritative native state is required')
    with np.load(path/'trajectory.npz') as archive:data={k:archive[k] for k in archive.files}
    neutral=data['arm'][0];native=data['ipc_arm'];mapping=np.argmin(np.linalg.norm(native[0,:,None]-neutral[None],axis=2),axis=0)
    if np.max(np.linalg.norm(native[0,mapping]-neutral,axis=1))>1e-7:raise ValueError('Native and skeleton rest surfaces differ')
    direction=native[:,mapping[4]]-native[:,mapping[0]]
    yaw=np.unwrap(np.arctan2(direction[:,1],direction[:,0]))
    # Rest pivot of this explicitly generated x-directed single-hinge rig.
    pivot=np.array([neutral[:,0].min(),neutral[:,1].mean(),neutral[:,2].mean()])
    local=neutral-pivot;output=[]
    for angle in yaw:
        c,s=np.cos(angle),np.sin(angle);rotation=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        output.append(local@rotation.T+pivot)
    output=np.asarray(output)
    deviation=float(np.linalg.norm(output-native[:,mapping],axis=2).max())
    data.update(output_arm=output,output_q_rad=yaw)
    np.savez_compressed(path/'joint_output.npz',**data)
    row={'state_source':'native ABD state at cloth timestamp','rotation_only':True,'fixed_pivot':pivot.tolist(),'bone_lengths_changed':False,'native_vs_rebuilt_corner_max_error_m':deviation,'raw_vs_output_q_max_difference_rad':float(np.max(np.abs(yaw-data['q_rad']))),'output_final_q_rad':float(yaw[-1])}
    (path/'joint_output.json').write_text(json.dumps(row,indent=2),encoding='utf-8');report['cases'][mode]=row
(folder/'joint_output_bridge.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
