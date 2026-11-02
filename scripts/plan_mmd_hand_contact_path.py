"""Plan a contact seed path on source hand meshes, with explicit failure output."""
import argparse,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.hand_contact_path import contact_seed_path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--rays',type=int,default=96);p.add_argument('--reuse-candidates');p.add_argument('--max-step',type=float,default=.018);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=Path(a.input).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
with np.load(folder/'source_hands.npz') as z:d={k:z[k] for k in z.files}
checksum=hashlib.sha256((folder/'source_hands.npz').read_bytes()).hexdigest();binding={'source_sha256':checksum,'source_path':str(folder/'source_hands.npz')};(out/'candidate_binding.json').write_text(json.dumps(binding,indent=2),encoding='utf-8');cached=None
if a.reuse_candidates:
    previous=Path(a.reuse_candidates).resolve();old=json.loads((previous/'candidate_binding.json').read_text())
    if old['source_sha256']!=checksum:raise ValueError('Candidate input hash mismatch')
    cached={i:np.load(previous/'candidate_layers'/f'{int(f)}.npy') for i,f in enumerate(d['frames'])}
report={'status':'RUNNING','actual_rig_applied':False,'gesture_accepted':False,'cloth_rebaked':False,'source_sha256':checksum,'max_local_step_limit_m':a.max_step};start=time.perf_counter()
def save():(out/'path_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def progress(kind,index,row):
    if kind=='candidate_layer':
        cache=out/'candidate_layers';cache.mkdir(exist_ok=True);np.save(cache/f"{int(d['frames'][index])}.npy",np.array(row['vectors']));return
    report['progress']={'kind':kind,'sample':index,'source_frame':int(d['frames'][index]),**row};save();print('HAND_PATH',kind,int(d['frames'][index]),json.dumps(row),flush=True)
try:
    source_separation=d['wrist_matrices'][:,0,:3,3]-d['wrist_matrices'][:,1,:3,3]
    delta,metrics=contact_seed_path(d['visible_hand_vertices'],d['ids_L'],d['ids_R'],d['faces_L'],d['faces_R'],d['wrist_matrices'][:,0,:3,:3],rays=a.rays,source_wrist_separation=source_separation,cached_layers=cached,max_local_step=a.max_step,progress=progress)
    metrics['side_policy']='Final left-minus-right wrist projection on declared left-wrist -Z remains at least 3 mm; not correction-sign restriction'
    vertices=d['visible_hand_vertices'].copy();vertices[:,d['ids_L']]+=delta[:,None]*.5;vertices[:,d['ids_R']]-=delta[:,None]*.5
    np.savez_compressed(out/'hand_seeds.npz',frames=d['frames'],relative_translation=delta,hand_vertices=vertices,source_frames=d['frames'],source_vertices=d['visible_hand_vertices'],ids_L=d['ids_L'],ids_R=d['ids_R'],faces_L=d['faces_L'],faces_R=d['faces_R'])
    report.update(status='CONTACT_GRAPH_PATH_REQUIRES_ACTUAL_RIG_AND_SUBFRAME_QA',**metrics)
except BaseException as exc:report.update(status='CONTACT_GRAPH_PATH_FAILED',error=repr(exc),traceback=traceback.format_exc());raise
finally:report['seconds']=time.perf_counter()-start;save()
