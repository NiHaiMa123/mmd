"""Collect the verified revised film and its exact replay/reproduction records."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args()
out=Path(a.delivery)
def read(name):return json.loads((out/name).read_text('utf8'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
pub=read('cache_publication.json');assert pub['status']=='COMPLETE_PHYSICAL_TRAJECTORY'
run=Path(pub['run']);result=json.loads((run/'result.json').read_text('utf8'));assert result['stage']=='COMPLETE'
native=read('native_geometry_audit.json');assert native['samples']==3593 and native['status']=='NATIVE_BLENDER_FULL_HEAD_SAMPLED_BODY_CONTACT_ROOT_REPLAY_PASS'
video=read('video_report.json');assert video['decoded_video_frames']==450 and video['algorithm_fingerprint']==pub['fingerprint']
blend=read('blend_delivery_report.json');assert blend['algorithm_fingerprint']==pub['fingerprint']
source=read('source_preservation.json');assert source['status']=='SOURCE_GEOMETRY_WEIGHTS_SHAPEKEYS_ACTIONS_AND_PROTECTED_BODY_PASS'
visual=read('visual_review.json');assert visual['status']=='NORMAL_FULL_CHARACTER_REVISED_SEQUENCE_REVIEW_PASS'
raw=read('raw_surface_11s/raw_surfaces.json');assert all(row['crossings']==0 for row in raw['rows'])
for name in ['config.json','input_fingerprint.json','result.json','progress_history.json']:
    shutil.copy2(run/name,out/('solver_config.json' if name=='config.json' else name))
pointer=json.loads((run/'latest_state.json').read_text('utf8'));assert pointer['sample']==3592
state=out/'cache/full_head_state_450.npz';shutil.copy2(pointer['path'],state)
with np.load(state) as z:
    assert int(z['index'])==3592 and str(z['fingerprint'])==pub['fingerprint']
    events=json.loads(str(z['contact_fallbacks']))
(out/'contact_projection_events.json').write_text(json.dumps(events,indent=2),'utf8')
paths=[out/'完整角色_整头连续物理_15秒.blend',Path(video['video']),Path(read('repro_bundle_report.json')['bundle']),*sorted((out/'cache').glob('*'))]
files=[dict(path=str(path.relative_to(out)),bytes=path.stat().st_size,sha256=sha(path)) for path in paths if path.is_file()]
manifest=dict(status='REVISED_FULL_CHARACTER_15S_RENDER_ENCODE_FULL_DECODE_AND_NATIVE_AUDIT_COMPLETE',algorithm_fingerprint=pub['fingerprint'],width=1920,height=1080,fps=30,frames=450,seconds=15,files=files,native_samples=3593,sample_step=.125,raw_skin_contact_11s=raw['rows'],visual_review=visual,protected_body_frames=[256,321],hair_vertices=24207,hair_triangles=40181,hard_roots=8994,physical_state_preserved=True,geometric_contact_projection_events=len(events),self_collision_solved=False,continuous_ccd_proven=False,source_body_fold_residuals_retained=True,clothing_paused=True,shutdown_configured=False,old_rejected_deliveries_preserved=True)
(out/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
print('REVISED_MATERIAL_FILM_DELIVERY_VERIFIED',flush=True)
