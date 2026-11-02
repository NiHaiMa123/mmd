"""Compare the reviewed bake with one native-collider refit; no simulation."""
import argparse
import json
import struct
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args()
root=Path(a.root);candidate=root/'candidate01'
def measurements(folder,prefix):
    rows=[]
    for letter in ['A','B']:
        rows.extend(json.loads((folder/f'{prefix}_{letter}/intrusion_measurement.json').read_text('utf8'))['frames'])
    rows.sort(key=lambda r:r['frame'])
    window=[r for r in rows if 226<=r['frame']<=450]
    assert [r['frame'] for r in window]==list(range(226,451))
    worst=max(window,key=lambda r:max(r['maximum_vertex_inward_depth_cm'],r['maximum_face_centroid_inward_depth_cm']))
    over=[r for r in window if max(r['maximum_vertex_inward_depth_cm'],r['maximum_face_centroid_inward_depth_cm'])>5]
    return dict(samples=len(window),source_frames=[226,450],
                maximum_depth_cm=max(worst['maximum_vertex_inward_depth_cm'],worst['maximum_face_centroid_inward_depth_cm']),
                worst_frame=worst['frame'],worst_seconds=worst['original_seconds'],
                frames_over_5cm=[r['frame'] for r in over],worst_frame_chains=worst['chains'],
                maximum_body_error_m=max(r.get('body_error_m',0) for r in rows),
                at_11s=next(r for r in rows if r['frame']==331),at_12_5s=next(r for r in rows if r['frame']==376))
baseline=measurements(root,'baseline_depth');result=measurements(candidate,'depth')
receipt=json.loads((candidate/'bake_report.json').read_text('utf8'))
profile=json.loads((root/'collider_profile.json').read_text('utf8'))
observation=json.loads((candidate/'collision_observation.json').read_text('utf8'))
assert receipt['collision_confirmed_in_every_observed_step']
caches=[]
for path in sorted((candidate/'cache').glob('*.pc2')):
    with path.open('rb') as stream:magic,version,points,start,step,samples=struct.unpack('<12siiffi',stream.read(32))
    assert magic==b'POINTCACHE2\0' and version==1 and path.stat().st_size==32+points*samples*12
    caches.append(dict(path=str(path),points=points,samples=samples,valid_header_and_length=True))
assert len(caches)==3
report=dict(status='STOPPED_RESIDUAL_INTRUSION_OVER_5CM' if result['frames_over_5cm'] else 'SAMPLED_DEPTH_LIMIT_PASS_REQUIRES_VISUAL_REVIEW',
            baseline=baseline,candidate=result,blend=receipt['blend'],
            standard_upstream_solver_unchanged=True,all_dynamics_parameters_preserved=True,
            one_time_native_sphere_primitives=len(profile['primitives']),actual_skin_inset_m=profile['actual_skin_inset_m'],
            initial_bone_point_contacts=len(profile['initial_contacts']),
            collision_response_frames=len(observation['responses']),
            native_collision_projections=sum(r['count'] for r in observation['responses'].values()),
            strain_flag_frames=len(receipt['strain_flags']),body_preserved=receipt['body_bone_max_error']==0 and receipt['body_skin_max_error_m']==0,
            caches=caches,full_video_render_started=False,naturalness_accepted=False,
            limitations='225 integer frames; all actual hair vertices and triangle centroids, not exact continuous-time or every-face-interior maximum; no self-collision proof.',
            shutdown_forbidden=True)
(root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(dict(status=report['status'],baseline_max_cm=baseline['maximum_depth_cm'],candidate_max_cm=result['maximum_depth_cm'],baseline_over_frames=len(baseline['frames_over_5cm']),candidate_over_frames=len(result['frames_over_5cm']),worst_frame=result['worst_frame'],worst_seconds=result['worst_seconds'],caches_valid=len(caches)),ensure_ascii=False))
