"""Publish an explicitly labelled physics/guard candidate, without fake QA."""
import argparse,json,struct,hashlib
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--out',required=True);p.add_argument('--frames');a=p.parse_args();run=Path(a.run);out=Path(a.out);out.mkdir(parents=True,exist_ok=True);src=Path(r'E:\project\mmd\work\headswap_xl_codex\fullhair_repro_20261030\input_body_aware');manifest=json.loads((src/'export_complete.json').read_text('utf8'));x=np.load(run/'positions.npy',mmap_mode='r');head=np.load(src/'anchors.npy',mmap_mode='r')[:,-1];cache=out/'cache/full_head.pc2';cache.parent.mkdir(exist_ok=True);assert not cache.exists(),'Preserve previous publication';frames=[float(v) for v in a.frames.split(',')] if a.frames else None
with cache.open('xb') as stream:
 stream.write(struct.pack('<12siiffi',b'POINTCACHE2\0',1,x.shape[1],0.,.125,len(x)));stream.truncate(32+x.size*4)
 samples=[round((f-1)*8) for f in frames] if frames else range(len(x))
 for k in samples:
  inv=np.linalg.inv(head[k]);local=x[k]@inv[:3,:3].T+inv[:3,3];stream.seek(32+k*x.shape[1]*12);stream.write(local.astype('<f4').tobytes())
def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(16*1024*1024),b''):h.update(block)
 return h.hexdigest()
if not frames:
 state=json.loads((run/'status.json').read_text('utf8'));rows=json.loads((run/'guard_rows.json').read_text('utf8'));assert state['stage']=='GEOMETRY_GUARD_COMPLETE_REQUIRES_NATIVE_AND_VISUAL_QA' and len(rows)==3593 and [r['sample'] for r in rows]==list(range(3593));assert all(r['crossings']==r['inside_vertices']==0 and .8995<=r['min_edge_ratio'] and r['max_edge_ratio']<=1.1005 for r in rows)
ROOT=Path(__file__).resolve().parents[1];P=src.parent.parent/'native_mmd_bridge_20261030/headless_bullet'
files=[ROOT/'tools/mmd_headless/package-lock.json',ROOT/'tools/mmd_headless/bake.mjs',ROOT/'tools/mmd_headless/node_modules/babylon-mmd/esm/Runtime/Optimized/wasm/spr/index_bg.wasm',ROOT/'scripts/evaluate_headless_hair.py',ROOT/'scripts/guard_headless_hair.py',P/'input/character_calibrated.pmx',P/'input/corrected_body_fk.vmd',P/'legal_start/joint_pivot_calibration.json',src.parent/'review_11s_20261030/hair_binding.npz',run/'positions.npy',src.parent/'dynamics_contact_islands/positions.npy',src/'body.npy',src/'anchors.npy']
files+=list((ROOT/'tools/contact_stack/mmd_hair_dynamics').glob('*.py'))
files+=[f for f in src.iterdir() if f.is_file() and f.suffix in ['.npy','.json'] and f not in files and f.name!='export_progress.json']
if (run/'component_fallback.json').exists():files.append(run/'component_fallback.json')
if (run/'temporal_filter.json').exists():files.extend([run/'temporal_filter.json',ROOT/'scripts/smooth_headless_hair_temporal.py',Path(json.loads((run/'temporal_filter.json').read_text('utf8'))['source'])/'positions.npy'])
provenance=dict(files={str(f):digest(f) for f in files},settings=dict(fps=30,physics_hz=240,gravity=[0,-98,0],compatibility_disable_offset=True,legal_initial_start=True,joint_pivot='calibrated child bone head',physics_gain=.25,geometry_guard='full display skin triangle and containment; original edges +/-10%; 8994 original fixed roots',reference_source='preserved validated contact corrections; old video not reused',ccd_proven=False,render_card_self_collision_solved=False));fingerprint=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest();(out/'algorithm_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),'utf8')
report=dict(status='KEYFRAME_CANDIDATE_REQUIRES_VISUAL_QA' if frames else 'COMPLETE_PHYSICAL_TRAJECTORY',fingerprint=fingerprint,input=str(src),run=str(run),cache=str(cache),published_through_sample=3592,published_through_frame=450,total_samples=3593,step=.125,hard_roots=int(np.load(src/'hard_roots.npy').sum()),all_head_parts_present=True,body_contact_verified_per_sample=not bool(frames),self_collision_solved=False,keyframes_only=frames,backend='babylon-mmd 1.3.0 Bullet WASM SPR, 240Hz; PMX child-bone pivot reconstruction; 25% physical secondary motion over preserved contact reference; finite-width geometry guard',resumable_bullet_velocity_state=False)
if (run/'component_fallback.json').exists():report['whole_clip_reference_fallback']=json.loads((run/'component_fallback.json').read_text('utf8'))
if (run/'temporal_filter.json').exists():report['temporal_filter']=json.loads((run/'temporal_filter.json').read_text('utf8'));report['backend']+='; automatic time-episode filtering and renewed finite-width contact projection'
(out/'cache_publication.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False))
