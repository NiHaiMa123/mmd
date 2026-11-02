"""Measure deformable attachment error; never equate solve exit with fit."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.contact_timeline import reference_times,reference_at_time
folder=Path(sys.argv[1]).resolve()
with np.load(folder/'trajectories.npz') as archive:data={k:archive[k] for k in ('cloth','pins','original_mapping','cloth_faces')}
actual=np.load(folder/'PPFCloth.npy');manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));times=reference_times(manifest,len(data['cloth']));fps=float(manifest['fps']);mapping=data['original_mapping'];indices=np.array([np.flatnonzero(mapping==i)[0] for i in range(len(data['pins']))]);actual=actual[:,indices];frames=len(actual);selected=data['pins']>.99999
if not selected.any():raise ValueError('No root attachment targets to measure')
status=json.loads((folder/'solve_status.json').read_text(encoding='utf-8'))
if status['status']!='FINISHED' or status.get('cache_frames')!=frames:raise ValueError('Feedback requires a complete, matched solver cache')
errors=np.stack([np.linalg.norm(actual[k,selected]-reference_at_time(data['cloth'],times,k/fps)[selected],axis=1) for k in range(frames)])
edges=np.unique(np.sort(np.concatenate((data['cloth_faces'][:,[0,1]],data['cloth_faces'][:,[1,2]],data['cloth_faces'][:,[2,0]])),axis=1),axis=0);rest=np.linalg.norm(actual[0,edges[:,0]]-actual[0,edges[:,1]],axis=1);ratios=np.linalg.norm(actual[:,edges[:,0]]-actual[:,edges[:,1]],axis=2)/np.maximum(rest,1e-9)
report=dict(scope='simulation proxy and root attachment targets; large lag alone does not establish blocked space or justify motion replanning',frames=frames,output_fps=fps,reference_samples=len(times),reference_timeline='interpolated at solver output times',frame_zero_mapping_max_error_m=float(np.max(np.abs(actual[0]-reference_at_time(data['cloth'],times,0)))),attachment_max_error_m=float(errors.max()),attachment_p95_error_m=float(np.quantile(errors,.95)),edge_ratio_min=float(ratios.min()),edge_ratio_max=float(ratios.max()),attachment_review_required=bool(errors.max()>.02),feedback_threshold_m=.02,per_frame_attachment_max_m=errors.max(axis=1).tolist(),contact_exemptions=0)
report['contact_exemptions']=status['contact_exemptions']
(folder/'attachment_feedback.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)}))
