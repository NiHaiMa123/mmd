"""Independent Blender surface + convex-box audits for the hand-contact fixture."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_contact import triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve()
reports={}
def crossing(a,fa,b,fb):
    ta=BVHTree.FromPolygons(a.tolist(),fa.tolist(),all_triangles=True);tb=BVHTree.FromPolygons(b.tolist(),fb.tolist(),all_triangles=True)
    return sum(triangle_crosses([Vector(v) for v in a[fa[i]]],[Vector(v) for v in b[fb[j]]]) for i,j in ta.overlap(tb))
def box_penetration(a,ra,b,rb):
    # Complete OBB separating-axis test, catches full containment as well.
    axes=[*ra.T,*rb.T,*[np.cross(x,y) for x in ra.T for y in rb.T]];depths=[]
    for axis in axes:
        length=np.linalg.norm(axis)
        if length<1e-8:continue
        axis=axis/length;pa=a@axis;pb=b@axis
        depths.append(min(pa.max()-pb.min(),pb.max()-pa.min()))
    return float(min(depths))
for mode in ('free','contact'):
    path=folder/mode
    if not (path/'report.json').exists():continue
    state=json.loads((path/'report.json').read_text(encoding='utf-8'))
    if state['status']!='RUN_COMPLETE_REQUIRES_AUDIT':raise ValueError(f'Incomplete mode {mode}')
    with np.load(path/'trajectory.npz') as z:d={k:z[k] for k in z.files}
    rows=[];maximum=0.
    for f in range(len(d['q'])):
        surfaces=[d[f'body_{i}'][f] for i in range(6)]+[d['root']];faces=[d[f'faces_{i}'] for i in range(6)]+[d['root_faces']];rotations=[*d['transforms'][f,:,:3,:3],np.eye(3)]
        crossings=0;overlaps=0;penetration=0.
        for i in range(7):
            for j in range(i+1,7):
                dep=box_penetration(surfaces[i],rotations[i],surfaces[j],rotations[j]);penetration=max(penetration,dep)
                if dep>1e-5:overlaps+=1
                crossings+=crossing(surfaces[i],faces[i],surfaces[j],faces[j])
        rows.append({'sample':f,'surface_crossings':crossings,'convex_overlaps':overlaps,'max_penetration_m':penetration})
        maximum=max(maximum,penetration)
        if f%50==0:print('BIMANUAL_AUDIT',mode,f,flush=True)
    left=d['transforms'][:,2];right=d['transforms'][:,5];rel=np.linalg.inv(left)@right;delta=np.linalg.inv(rel[0])@rel
    pos=float(np.linalg.norm(delta[:,:3,3],axis=1).max());angle=float(np.arccos(np.clip((np.trace(delta[:,:3,:3],axis1=1,axis2=2)-1)*.5,-1,1)).max());centre=(left[:,:3,3]+right[:,:3,3])*.5;motion=float(np.linalg.norm(centre-centre[0],axis=1).max())
    native_error=max(float(np.linalg.norm(d[f'body_{i}']-d[f'native_{i}'],axis=-1).max()) for i in range(6));clear=all(r['surface_crossings']==0 and r['convex_overlaps']==0 for r in rows)
    passed=clear and pos<.001 and angle<np.deg2rad(1) and motion>.02 and native_error<.001 and state['root_translation_m']==0 and state['joint_limit_violations']==0
    report={'status':'PERSISTENT_HAND_CONTACT_PROXY_SAMPLED_PASS' if passed and mode=='contact' else 'CONTROL_MODE' if mode=='free' else 'CONTACT_CASE_NOT_ACCEPTED','samples':len(rows),'surface_crossing_samples':sum(r['surface_crossings']>0 for r in rows),'convex_overlap_samples':sum(r['convex_overlaps']>0 for r in rows),'max_penetration_m':maximum,'max_relative_hand_position_error_m':pos,'max_relative_hand_rotation_error_rad':angle,'hand_center_max_motion_m':motion,'max_native_actual_error_m':native_error,'root_translation_m':state['root_translation_m'],'joint_limit_violations':state['joint_limit_violations'],'rows':rows}
    (path/'surface_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');reports[mode]={k:v for k,v in report.items() if k!='rows'}
if set(reports)=={'free','contact'}:
    good=reports['contact']['status']=='PERSISTENT_HAND_CONTACT_PROXY_SAMPLED_PASS' and reports['free']['max_relative_hand_position_error_m']>.01
    summary={'status':'BIMANUAL_CONTACT_CONTROLLED_PROXY_PASS' if good else 'BIMANUAL_CONTACT_NOT_ACCEPTED','scope':'Declared persistent contact, six planar joints; no fingers, phase detection/release, cloth or full MMD acceptance','modes':reports}
else:summary={'status':'MISSING_CONTROL_RUN','modes':reports}
(folder/'comparison.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('BIMANUAL_CONTACT_AUDIT',json.dumps(summary),flush=True)
