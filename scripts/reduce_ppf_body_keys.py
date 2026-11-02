"""Compress prescribed body time keys; retain all geometry and hair-root keys."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from animation_contact_tools.trajectory_keys import reduce_trajectory_keys
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--tolerance',type=float,default=.0001);a=p.parse_args();root=Path(a.input)
if (root/'body_key_indices.npy').exists():raise ValueError('Existing body key selection; use a fresh input directory')
manifest=json.loads((root/'manifest.json').read_text('utf8'));data=np.load(root/'trajectories.npz');keys,report=reduce_trajectory_keys(data['body'],manifest['sample_times_s'],a.tolerance);np.save(root/'body_key_indices.npy',keys);report.update(all_body_vertices_and_faces_preserved=True,all_hair_root_keys_preserved=True,actual_display_mesh_audit_required=True)
(root/'body_key_reduction.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('BODY_KEY_REDUCTION',json.dumps(report),flush=True)
