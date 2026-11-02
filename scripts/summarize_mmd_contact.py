"""Conservative acceptance summary of actual MMD contact work, not cloth success."""
import json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'outputs/contact_stack';static=folder/'mmd_grouped_keyposes_v2';qa=json.loads((static/'reload_qa.json').read_text());solve=json.loads((static/'keypose_report.json').read_text());images=sorted((static/'review').glob('*.png'))
def png_size(path):
    with path.open('rb') as f:header=f.read(24)
    if header[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('Not a PNG')
    return struct.unpack('>II',header[16:24])
checks={'three_static_actual_skin_contacts':qa['status']=='SAVED_STATIC_CONTACT_GEOMETRY_PASS_GESTURE_UNREVIEWED','original_24_meshes_and_morphs':qa['protected_meshes_and_morphs']==24,'original_action_preserved':qa['original_action_preserved'],'hand_audit_matches_visible':all(v['after']['audit_vs_visible_hand_max_error_m']==0 for v in qa['frames'].values()),'head_torso_feet_world_poses':all(v['after']['primary_world_matrix_error']==0 for v in qa['frames'].values()),'eighteen_native_1080p_views':len(images)==18 and all(png_size(p)==(1920,1080) for p in images)}
graphs={}
for name in ('mmd_hand_graph_v1','mmd_hand_graph_v2','mmd_hand_graph_v3','mmd_hand_graph_v4','mmd_hand_graph_v5'):
    path=folder/name/'path_report.json'
    if path.exists():graphs[name]={'solver_status':json.loads(path.read_text())['status'],'accepted_as_actual_motion':False,'contact_order_rejected':name=='mmd_hand_graph_v1'}
report={'status':'MMD_STATIC_GROUPED_CONTACT_PASS_CONTINUOUS_CLOTH_INCOMPLETE' if all(checks.values()) else 'MMD_STATIC_CONTACT_NOT_ACCEPTED','accepted_as_full_dynamic_outfit':False,'accepted_as_motion_correction':False,'gesture_preservation':'REQUIRES_VISUAL_REVIEW','full_physics_backend_connected_to_MMD':False,'cloth_rebaked':False,'old_clasp_candidate_accepted':False,'checks':checks,'static_frames':[310,325,340],'static_file':str(static/'MMD_Contact_Keyposes.blend'),'continuous_graphs':graphs,'remaining':['Continuous actual MMD skin and subframe validation with declared hand order','Contact entry/exit, rolling, finger collision and anatomical limits','Full character self contact and all garment layers with same-time physics feedback','Complete 15-second multiview and gesture acceptance']}
(folder/'mmd_contact_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if not all(checks.values()):raise SystemExit(1)
