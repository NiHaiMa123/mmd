"""Embed the source hair and prescribe all cells containing true rigid roots."""
import argparse,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
# Load the NumPy-only helper without initializing the Blender addon package.
import importlib.util
spec=importlib.util.spec_from_file_location('tet_volume_binding',ROOT/'addon/animation_contact_tools/tet_volume_binding.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.input);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():raise ValueError('Use a fresh embedded volume directory')
manifest=json.loads((src/'manifest.json').read_text('utf8'));run=Path(manifest['source_run']);r=json.loads((run/'report.json').read_text('utf8'))
with np.load(src/'trajectories.npz') as z:d={k:z[k] for k in z.files}
with np.load(run/'dense_motion.npz') as z:heads=z['anchor_matrices']
with np.load(ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle/left_rig_root_native/initial_projection.npz') as z:initial={k:z[k] for k in z.files}
first=manifest['source_frames'][0];delta=heads[round((first-r['frames'][0])/r['step_frames'])]@np.linalg.inv(heads[0]);points=initial['coordinates']@delta[:3,:3].T+delta[:3,3];binding=helper.bind_volume(points,d['cloth'][0],d['tetrahedra']);roots=np.unique(binding['vertex_indices'][initial['pinned']]);d['pins'][roots]=1.;np.savez_compressed(out/'trajectories.npz',**d);np.savez_compressed(out/'volume_binding.npz',**binding,source_ids=initial['ids'],pinned=initial['pinned'],rest_coordinates=initial['original'],initial_coordinates=initial['coordinates']);manifest['embedded_display']=dict(method='contained nonnegative tetrahedral barycentric coordinates',source_vertices=len(points),true_rigid_source_roots=int(initial['pinned'].sum()),prescribed_volume_vertices=int((d['pins']>.999).sum()),reconstruction_error_m=binding['reconstruction_error_m'],minimum_barycentric=binding['minimum_unclamped_barycentric']);(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');print('VOLUME_EMBEDDING',json.dumps(manifest['embedded_display']),flush=True)
