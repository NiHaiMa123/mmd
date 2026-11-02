"""Independent triangle audits of actual multi-link, body and cloth surfaces."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve();state=json.loads((folder/'report.json').read_text(encoding='utf-8'))
if state['status']!='RUN_COMPLETE_REQUIRES_AUDIT':raise ValueError('Incomplete simulation is not an audit input')
with np.load(folder/'trajectory.npz') as archive:d={k:archive[k] for k in archive.files}
def crossing(a,fa,b,fb,self_pair=False):
    ta=BVHTree.FromPolygons(a.tolist(),fa.tolist(),all_triangles=True);tb=ta if self_pair else BVHTree.FromPolygons(b.tolist(),fb.tolist(),all_triangles=True);count=0
    for i,j in ta.overlap(tb):
        if self_pair and (i>=j or set(fa[i])&set(fb[j])):continue
        if triangle_crosses([Vector(v) for v in a[fa[i]]],[Vector(v) for v in b[fb[j]]]):count+=1
    return count
cloth=[key for key in d if key.startswith('cloth_') and len(key.split('_'))==2];rows=[]
for frame in range(len(d['q'])):
    row={'sample':frame,'source_arm_head':sum(crossing(d[f'source_body_{i}'][frame],d['body_faces'],d['head'],d['head_faces']) for i in range(2)),
        'arm_head':sum(crossing(d[f'body_{i}'][frame],d['body_faces'],d['head'],d['head_faces']) for i in range(2)),
        'arm_torso':sum(crossing(d[f'body_{i}'][frame],d['body_faces'],d['torso'],d['torso_faces']) for i in range(2)),
        'upper_forearm':crossing(d['body_0'][frame],d['body_faces'],d['body_1'][frame],d['body_faces']),
        'body_cloth':sum(crossing(d[f'body_{i}'][frame],d['body_faces'],d[c][frame],d['cloth_faces_'+c.split('_')[-1]]) for i in range(2) for c in cloth),
        'primary_cloth':sum(crossing(d[part],d[part+'_faces'],d[c][frame],d['cloth_faces_'+c.split('_')[-1]]) for part in ('head','torso') for c in cloth),
        'cloth_self':sum(crossing(d[c][frame],d['cloth_faces_'+c.split('_')[-1]],d[c][frame],d['cloth_faces_'+c.split('_')[-1]],True) for c in cloth),
        'cloth_layers':sum(crossing(d[c][frame],d['cloth_faces_'+c.split('_')[-1]],d[e][frame],d['cloth_faces_'+e.split('_')[-1]]) for j,c in enumerate(cloth) for e in cloth[j+1:])}
    rows.append(row)
    if frame%30==0:print('ARTICULATED_AUDIT',frame,flush=True)
deviations=[]
for i in range(2):
    actual=d[f'body_{i}'];native=d[f'native_{i}'];indices=np.argmin(np.linalg.norm(native[0,:,None]-actual[0,None],axis=-1),axis=0);deviations.append(float(np.linalg.norm(native[:,indices]-actual,axis=-1).max()))
attachments=[]
for entry in state.get('attachments',{}).get('entries',[]):
    cloth_co=d['cloth_'+str(entry['cloth_entity_index'])][:,entry['cloth_vertex']];body_co=d['native_1'][:,entry['body_vertex']];error=np.abs(np.linalg.norm(cloth_co-body_co,axis=-1)-entry['rest_length_m']);attachments.append({'max_separation_error_m':float(error.max()),'cloth_anchor_max_motion_m':float(np.linalg.norm(cloth_co-cloth_co[0],axis=-1).max())})
counts={key:sum(row[key]>0 for row in rows) for key in rows[0] if key!='sample'}
accepted=all(value==0 for key,value in counts.items() if key!='source_arm_head') and state['head_max_translation_m']==0 and state['torso_max_translation_m']==0 and state['joint_limit_violations']==0 and max(deviations)<.001 and max((e['max_separation_error_m'] for e in attachments),default=0)<.001
report={'status':'MULTI_LINK_PROXY_CASE_SAMPLED_PASS' if accepted else 'PROXY_CASE_NOT_ACCEPTED','scope':'Two revolute joints, fixed head/torso, moving two-layer cloth; sampled proxy checks are not full MMD or CCD proof','samples':len(rows),'crossing_samples':counts,'head_translation_m':state['head_max_translation_m'],'torso_translation_m':state['torso_max_translation_m'],'max_native_actual_corner_error_m':max(deviations),'attachment_metrics':attachments,'joint_limit_violations':state['joint_limit_violations'],'rows':rows}
(folder/'surface_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('ARTICULATED_CONTACT_AUDIT',json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)
