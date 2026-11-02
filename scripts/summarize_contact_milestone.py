"""Record measured partial acceptance; full garment coupling remains incomplete."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'outputs/cynical_cloth15/contact_motion'
out=base/'body_contact_v1'
probe=base/'sequence_v5/temporal/ppf/coherent_probe_untangled_clean'
read=lambda path:json.loads(path.read_text(encoding='utf-8'))
qa=read(out/'dense_contact_qa.json')
local=read(out/'subframe_repair.json')
video=read(out/'comparison_video.json')
solve=read(probe/'solve_status.json')
feedback=read(probe/'attachment_feedback.json')
classification=read(probe/'feedback_classification.json')
reload=read(probe/'probe_preview_qa.json')
hard=read(out/'ppf/layered15_body_untangled/untangle_report.json')
soft=read(out/'ppf/layered15_body_soft_untangled/untangle_report.json')
strict=read(out/'ppf/layered15_untangled_clean/solve_status.json')
diagnostics=read(out/'ppf/layered15_untangled_clean/input_diagnostics.json')
envelope=read(out/'ppf/layered15_untangled_clean_skirt_envelope/skirt_initialization.json')
archive=ROOT/'dist/mmd_outfit_bridge-0.9.0-motion-contact-20261027.zip'
assert qa['after']['crossing_samples']==0 and local['remaining_local_crossing_samples']==0
assert qa['original_action_preserved'] and qa['foot_max_matrix_difference']==0
assert solve['status']=='FINISHED' and solve['contact_exemptions']==0 and not solve['allow_intersection']
assert max(reload['cache_reload_errors_m'].values())==0
stream=next(s for s in video['streams'] if s['codec_type']=='video')
assert (stream['width'],stream['height'],stream['nb_frames'])==(1920,1080,'90')
for asset in (out/'ContactMotion.blend',out/'ContactMotion_8_11s_1080p.mp4',probe/'PhysicsContactProbe_2s.blend',probe/'PhysicsProbeClothLocal.pc2',archive):
    assert asset.is_file(),asset
report={
    'status':'GESTURE_REJECTED_GEOMETRY_SAMPLED_PASS_CLOTH_INCOMPLETE',
    'accepted_as_full_dynamic_outfit':False,
    'accepted_as_motion_correction':False,
    'semantic_acceptance':{
        'status':'USER_REJECTED',
        'gesture_preservation':'FAIL',
        'reason':'The user rejected the crossed-hands/clasp gesture: avoiding intersections changed the intended gesture.',
        'required_policy':'Preserve intended hand contact, relative orientation and arm crossing order; reject infeasible candidates rather than silently splitting hands.',
        'reference':'docs/CONTACT_SEMANTICS_RESEARCH_2026-10-27.md'},
    'motion_file':str(out/'ContactMotion.blend'),
    'body_contact':{
        'visible_frames':[47,496],'fps':30,'sample_step_frames':qa['sample_step_frames'],
        'before':qa['before'],'after':qa['after'],
        'local_refinement_samples':len(local['local_samples']),
        'local_refinement_crossing_samples':local['remaining_local_crossing_samples'],
        'protected_meshes_and_morphs':qa['protected_meshes_and_morphs'],
        'original_action_preserved':qa['original_action_preserved'],
        'foot_max_matrix_difference':qa['foot_max_matrix_difference'],
        'scope':qa['scope'],
        'limitations':['Not continuous collision detection','Same-hand fingers, same-arm internal contacts, hair and decorations not covered','Hand gestures changed; wrist continuity and anatomical limits not fully accepted','Old world-space garment caches disabled; not a new dressed final film']},
    'comparison_video':{'path':str(out/'ContactMotion_8_11s_1080p.mp4'),'width':1920,'height':1080,'fps':30,'frames':90,'seconds':3,'audio':False,'scope':'8-11 seconds of body motion; sleeves hidden for inspection'},
    'numerical_cloth_body_probe':{
        'path':str(probe/'PhysicsContactProbe_2s.blend'),'cache':str(probe/'PhysicsProbeClothLocal.pc2'),
        'cache_frames':solve['cache_frames'],'sample_time_span_s':59/30,'preroll_s':46/30,
        'contact_exemptions':solve['contact_exemptions'],'allow_intersection':solve['allow_intersection'],
        'attachment_max_error_m':feedback['attachment_max_error_m'],
        'attachment_p95_error_m':feedback['attachment_p95_error_m'],
        'edge_ratio':[feedback['edge_ratio_min'],feedback['edge_ratio_max']],
        'contact_blocked_goals':classification['contact_blocked_goals'],
        'motion_replan_recommended_by_probe':classification['motion_replan_recommended'],
        'cache_reload_max_error_m':max(reload['cache_reload_errors_m'].values()),
        'scope':'Low-resolution sleeve/skirt proxy; prescribed skin collider; fixed clothing visual reference; not full-layer or full-15s acceptance'},
    'full_layer_attempt':{'strict_native_status':strict['status'],'strict_native_error':strict['error'],
        'body_aware_hard_root_remaining':hard['remaining'],'body_aware_soft_root_remaining':soft['remaining'],
        'body_aware_soft_root_converged':soft['converged'],
        'strict_native_cloth_components':diagnostics['cloth_collider_components'],
        'rejected_skirt_envelope':envelope,
        'two_way_cloth_pressure_to_bone_motion_complete':False},
    'addon':{'path':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_import_and_registration_smoke':'PASS','interface':'Experimental Python modules; not wired to the old fit button'},
    'verification':['Blender motion geometry contract PASS','Scoped broadphase contract PASS (213 matching brute-force pairs)','Contact timeline: 3 tests PASS','Independent ZIP import, registration, scene preservation PASS'],
    'next_required':['Classify incidental collisions, intentional contacts and deformable contacts before solving','Reconstruct and validate the original crossed-hands/clasp gesture with paired-hand and elbow constraints','Resolve initial skirt / fixed-garment contact and layer order','Recompute full garment contacts against a semantically accepted motion','Implement and validate contact-triggered skeletal replanning with a second cloth solve','Validate high-resolution transfer, motion quality, fingers, hair and decorations separately']}
(out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(report['status'])
print(out/'acceptance.json')
