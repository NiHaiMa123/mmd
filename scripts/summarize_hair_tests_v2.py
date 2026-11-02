"""Case evidence, including explicit invalidation of the earlier empty-world runs."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=base/'hair_tests_v2'
def read(path):return json.loads(Path(path).read_text('utf8'))
track=read(out/'continuation_witness_15/hair_track_report.json');reviews=read(out/'review1080_verified/review.json');backend={}
for name in ('mmd_world_verified','mmd_world_surface'):
 r=read(out/name/'hair_backend_probe.json');assert r['setup']['world_rigid_members']==185;assert r['setup']['verified_disabled_hair_pairs']==r['setup']['expected_disabled_hair_pairs']==9630
 backend[name]={'setup':r['setup'],'frames_simulated':[1,450],
 'audited_frames':[s['frame'] for s in r['samples']],
 'body_skin_max_error_m':max(s['body_skin_max_error_m'] for s in r['samples']),
 'valid_edge_ratio_peak':max(s['valid_edge_ratio_max'] for s in r['samples']),
 'last_valid_edge_ratio_max':r['samples'][-1]['valid_edge_ratio_max'],
 'last_valid_edge_ratio_p99':r['samples'][-1]['valid_edge_ratio_p99'],
 'some_pair_counts_capped':any(p['count_is_lower_bound'] for s in r['samples'] for p in s['pairs']),
 'actual_surface_full_counts_at_review_frames':[x for x in reviews if x['name'].startswith('bullet' if name=='mmd_world_verified' else 'surface')],
 'complete_hair_accepted':False}
invalid=[str(p) for p in out.glob('mmd_*') if p.is_dir() and not p.name.startswith('mmd_world_')]+[str(base/'native_hair_probe')]
report={'status':'HAIR_UNRESOLVED','source':str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),
 'original_source_overwritten':False,'complete_hair_accepted':False,
 'invalidated_earlier_bullet_experiments':{'directories':invalid,'reason':'RigidBody properties existed but RigidbodyWorld.collection was None; prior mode/filter comparisons were not valid Bullet dynamics evidence. Geometry observations remain diagnostics only.'},
 'bone_projection':{'sample_count':len(track['samples']),'zero_target_crossing_keyposes':sum(s['hair_target_crossings']==0 for s in track['samples']),
 'keyposes_with_edges_within_10_percent':sum(.9<s['min_edge_ratio'] and s['max_edge_ratio']<1.1 for s in track['samples']),
 'layer_reload_error_m':track['layer_max_error_m'],'primary_matrix_error':track['primary_bone_matrix_error'],'protected_skin_error_m':track['protected_skin_max_error_m'],
 'candidate':str(out/'continuation_witness_15/HairContact_ContinuationCandidate.blend'),
 'visual_failure':'Front lock forms a spike at frame 240; target crossings remain. 35 keyposes are not full-frame or CCD acceptance.'},
 'verified_bullet':backend,'review':reviews,'portable_tests':{
 'body_contact':read(ROOT/'outputs/portable_contact_contract/report.json'),
 'hair_jacobian':read(ROOT/'outputs/portable_hair_jacobian/report.json'),
 'physics_world':read(ROOT/'outputs/physics_world_contract/report.json'),
 'packaged_hair_cli':read(out/'cli_package_probe/job_status.json')},
 'open_issues':['head/scalp embedded attachments are audited but not accepted','open-region containment is incomplete','hair self-collision not solved','sampling is not CCD','mid-motion strain and hair/body crossings remain','original clasp window protected; original body transition and hip failures remain'],
 'bilibili':{'project_used':'E:/project/bilibili','search_unique_candidates':51,'metadata_is_video_evidence':False,
 'read_videos':[{'bvid':'BV1PZ421T7Yj','evidence':'platform_subtitle','time':'07:14','finding':'Try physics + bones; sequential simulation and rebake after motion changes'},
 {'bvid':'BV16eJBzGEGy','evidence':'ocr','time':'01:07–02:31','finding':'Check actual Blender collision collections. 04:01–04:19 disabling hand/skirt collisions rejected for this task'},
 {'bvid':'BV1Bi1HBTELx','evidence':'platform_subtitle','time':'00:02–01:04','finding':'MMD bridge exports baked physics; not universal surface penetration repair'},
 {'bvid':'BV1Fj411b77p','evidence':'platform_subtitle','time':'09:29–10:41','finding':'Particle Instance driven cards with particle Hair Dynamics; needs adaptation for arbitrary PMX mesh'}]}}
(out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'status':report['status'],'bone_keypose_passes':report['bone_projection']['zero_target_crossing_keyposes'],'invalidated_old_bullet_directories':len(invalid),'review_images':sum(len(r['images']) for r in reviews)},ensure_ascii=False))
