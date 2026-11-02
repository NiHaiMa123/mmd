"""Collect the scoped evidence without turning sampled passes into full acceptance."""
import json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/hair_arm_feedback_20261028'
def read(path):return json.loads((out/path).read_text('utf8'))
hair=read('guarded_bundle/independent_validation.json')
body=read('baked_polished/independent_body_validation.json')
arm=read('baked_polished/arm_detour_report.json')
route=read('planned_route/planned_route.json')
probe=shutil.which('ffprobe')
if not probe:raise RuntimeError('ffprobe is required to verify the delivered movie')
movie=out/'Arm_Hair_Contact_Comparison_1080p.mp4'
video=json.loads(subprocess.check_output([probe,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames:format=duration','-of','json',str(movie)],text=True))
stream=video['streams'][0]
assert (stream['width'],stream['height'],stream['r_frame_rate'],int(stream['nb_read_frames']))==(1920,1080,'30/1',153)
assert hair['selected_bundle_samples_pass'] and hair['failed_samples']==0
assert body['failed_samples']==0 and body['source_actions_hash_match']
assert all(body[k]==0 for k in ['primary_matrix_error','unaffected_skin_error_m','outside_phase_mesh_error_m','clasp_window_checked_mesh_error_m'])
result={'status':'LOCAL_ARM_HAIR_SAMPLED_PASS_GLOBAL_UNRESOLVED','accepted':False,
 'selected_bundle':{'frames':[200,250],'sample_count':hair['sample_count'],'step_frames':hair['sample_step'],'failed_samples':hair['failed_samples'],'edge_ratio':[hair['min_mesh_edge_ratio'],hair['max_mesh_edge_ratio']],'root_error_m':hair['interpolated_root_error_peak_m']},
 'right_arm':{'frames':[212,228],'verification_step_frames':body['sample_step_frames'],'failed_samples':body['failed_samples'],'max_wrist_offset_m':route['max_offset_m'],'world_wrist_heading_error_degrees':arm['wrist_world_heading_error_degrees'],'original_actions_hash_match':True,'original_action_count':body['original_action_count'],'protected_window':[256,321],'protected_mesh_checks':[256,285,321]},
 'video':{'path':str(movie),'slow_motion_factor':3,**video},
 'candidate':hair['candidate'],'cache':hair['cache']['cache'],
 'whole_hair_solved':False,'hair_self_collision_tested':False,'full_preroll_performed':False,'ccd_proven':False,'motion_naturalness_accepted':False,
 'open_region_containment_fully_checked':False,'other_existing_body_failures_fixed':False,
 'visual_review':'front/side/oblique critical poses, 214-222 transition sequence, encoded movie frame; no full naturalness acceptance',
 'new_core_contracts':['root_envelope_contract','two_bone_goal_contract','arm_route_contract'],
 'generic_selector_case_replay':'exactly matched the already simulated waypoint sequence',
 'plugin_package':str(ROOT/'dist/animation_contact_tools-0.1.3.zip')}
(out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k not in ('video','visual_review')},ensure_ascii=False))
