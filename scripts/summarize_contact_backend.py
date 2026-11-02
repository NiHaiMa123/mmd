"""Summarize the measured backend milestone without accepting the full system."""
import hashlib,importlib.metadata,json,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'outputs/contact_stack/joint_axis_sync_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
physical=read(folder/'comparison_physics_output.json');raw=read(folder/'comparison.json');bridge=read(folder/'joint_output_bridge.json');playback=read(folder/'blender_playback_qa.json');video=read(folder/'video_report.json');shapes=read(folder/'two_way/cloth_shape_metrics.json')
assert physical['status']=='PHYSICS_JOINT_OUTPUT_SAMPLED_PASS_LIVE_POSE_MISMATCH'
assert raw['status']=='PROBE_NOT_ACCEPTED'
assert physical['modes']['two_way']['samples']==91 and physical['modes']['two_way']['max_fixed_pin_error_m']==0
assert playback['bone_and_cloth_max_error_after_reload_m']<1e-6 and video['decode_verified']
doctor=(ROOT/'tools/contact_stack/uipc_doctor.log').read_text(encoding='utf-8')
assert '[OK  ] CUDA engine probe:' in doctor and '[FAIL' not in doctor
scripts=('probe_genesis_ipc.py','run_genesis_contact_matrix.py','genesis_ipc_constraints.py','audit_genesis_ipc.py','export_genesis_joint_pose.py','preview_contact_backend.py','encode_contact_backend.py')
report={
 'status':'LIMITED_BACKEND_OUTPUT_PROBE_PASS_FULL_MMD_SYSTEM_INCOMPLETE',
 'full_system_accepted':False,'mmd_character_integrated':False,'raw_genesis_live_pose_accepted':False,
 'runtime':{'python':sys.version,'platform':platform.platform(),'packages':{k:importlib.metadata.version(k) for k in ('genesis-world','pyuipc','quadrants','torch','numpy')},'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],text=True).strip(),'cuda_doctor':'PASS','rigid_backend':'CPU','ipc_backend':'CUDA'},
 'scenario':{'sample_time_span_s':.9,'samples':91,'dt_s':.01,'joint':'one fixed-base revolute','cloth_layers':2,'vertices_per_layer':169,'world_fixed_cloth_pins':26,'friction_enabled':True,'contact_enabled':True,'contact_exemptions':0},
 'evidence':{'physical_output':physical,'raw_live_pose':raw,'single_hinge_output_bridge':bridge,'blender_playback':playback,'cloth_shape':shapes},
 'artifacts':{'blender':str(folder/'Backend_JointCloth_Probe.blend'),'video':str(folder/'Backend_JointCloth_1080p.mp4'),'video_resolution':[1920,1080],'video_frames':91,'video_fps':30,'video_is_slowed_numerical_demonstration':True},
 'coverage':{'body_cloth_feedback':'LIMITED_NUMERICAL_PROBE_PASS','two_cloth_layers_and_fixed_edges':'LIMITED_NUMERICAL_PROBE_PASS','bone_playback_from_same_native_timestamp':'SINGLE_HINGE_PASS','body_self_collision_on_character':'NOT_TESTED','limb_limb_collision_on_character':'NOT_TESTED','preserve_intentional_contacts':'NOT_IMPLEMENTED_PREVIOUS_GESTURE_REJECTED','animated_garment_attachments':'NOT_IMPLEMENTED','full_high_resolution_MMD':'NOT_TESTED'},
 'limitations':['Native axis direction needed a version-pinned adapter','Raw live Genesis pose still differs from native body/cloth timestamp; it is not accepted','Output bridge only reconstructs this fixed-pivot, fixed-length single hinge','Fixed pins are world-fixed test anchors, not animated MMD attachments','Sampled reconstructed surfaces are not a CCD proof for arbitrary skeletal interpolation','No new 15-second character film or repaired clasp has been produced'],
 'script_sha256':{name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest() for name in scripts}}
(folder/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report['status']);print(folder/'acceptance.json')
