"""Publish explicit rejection state for this real-character fitting experiment."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'outputs/contact_stack/outfit_body_contact_v1'
reasons={
    'contact_fit':'Residual crossings and unacceptable local stretch',
    'arap_fit':'Residual crossings and garment shape damage',
    'arap_persistent':'Main cloth/nylon not clear; lining-only crossing count is not full containment acceptance',
    'envelope_fit':'Spikes and large anatomical-envelope deformation',
    'skeletal_field':'Residual crossings and excessive movement',
    'closed_skin':'Proxy does not enclose original skin',
    'filled_skin':'Nylon/skin clear but nylon/shoes 16820 crossings; proxy has nonmanifold connections',
    'closed_projection':'Residual garment/body intersections',
    'component_fit':'Unresolved garment pieces',
    'component_roll_fit':'Unresolved garment pieces',
    'live_skin_binding':'Residual collisions and triangle-frame distortion',
    'live_skin_binding_v2':'Not a complete collision-free garment',
    'composed_dense':'2206 main cloth/body and 7 lining/body crossings; shape damage',
    'smooth_skin':'6287 main cloth/body crossings',
    'smooth_parts':'Unresolved pieces',
    'cages':'3165 main cloth/body crossings; visible inflation',
    'skinning_only':'Diagnostic without cloth dynamics; residual garment/body and new nylon/shoe collisions',
    'smooth_no_cache':'Diagnostic baseline only; not a collision repair',
    'no_cache_parts':'Unresolved pieces; not a complete garment',
    'bounded_wrap':'Excessive displacement and residual crossings',
    'bounded_normal_wrap':'Excessive displacement, greatly increased triangle crossings',
    'rebuilt_layers':'Texture/material/coverage damage; residual sleeve/skirt crossings',
    'rebuilt_layers_uv_v2':'Texture/material/coverage damage persists; not accepted',
    'no_cache_dense':'2647 main cloth/body and 5 lining/body crossings; shape damage',
    'rigid_sleeve_templates':'Neither full sleeve template resolved',
    'rigid_puff_templates':'Local domain check included tail probes; superseded by v2 and not accepted',
    'rigid_puff_templates_v2':'Neither upper sleeve template resolved in the tested shape family',
}
preservation=json.loads((out/'source_preservation.json').read_text(encoding='utf8'))
audit=json.loads((out/'final_audit_rejected/audit.json').read_text(encoding='utf8'))
report={'status':'OUTFIT_CONTACT_NOT_FIXED_CANDIDATES_REJECTED','accepted':False,'accepted_output':None,'promoted_to_user_blender':False,'priority':'garment/body contact; fist work deferred by user','gesture':'USER_REJECTED_NOT_A_FIST','frame':325,'complete_15s_rebaked':False,'new_dynamic_cloth_solve':False,'source_preservation':preservation,'last_dense_candidate':{name:{'true_crossings':row['true_crossings'],'buried_vertex_probe':row.get('buried_vertex_probe')} for name,row in audit['frames']['325'].items() if name in ('Cloth','SleeveLining','Stockings')},'new_nylon_shoe_crossings':16820,'candidates':{name:{'accepted':False,'reason':reason} for name,reason in reasons.items() if (out/name).exists()},'next_required':['Repair source garment shape, attachment and layer order while preserving appearance','Check all skin faces, whole-surface burial, cloth layers and shoes together','Validate difficult motion window before rebaking and reviewing full 15 seconds']}
(out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
root=ROOT/'outputs/contact_stack/mmd_contact_acceptance.json';state=json.loads(root.read_text(encoding='utf8'));state.update(status='USER_REJECTED_GESTURE_OUTFIT_CONTACT_NOT_FIXED',gesture_preservation='USER_REJECTED_NOT_A_FIST',accepted_as_motion_correction=False,accepted_as_full_dynamic_outfit=False,current_priority='Fix garment/body contact before fist gesture',outfit_contact_report=str(out/'acceptance.json'));state['historical_checks_notice']='Earlier three-pose body-region checks are limited historical evidence; they do not accept the gesture, garment, all skin boundaries, or dynamics.';root.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
print(report['status'],len(report['candidates']),'rejected/not accepted candidates')
