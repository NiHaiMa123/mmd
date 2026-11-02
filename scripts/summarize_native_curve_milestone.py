import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028/hair_curves_20261028'
def read(path):return json.loads(Path(path).read_text('utf8'))
tests={}
for name in ('curve_native_control','curve_native_collision','curve_native_refined','curve_native_high_accuracy','portable_zip_benchmark','portable_margin3_a','portable_margin3_b'):
 r=read(out/name/'report.json');tests[name]={k:r[k] for k in ('metadata','benchmark_pass','min_edge_ratio','max_edge_ratio','max_root_error_m','min_segment_clearance_m','min_interpolated_clearance_m','seconds')}
assert tests['portable_margin3_a']['benchmark_pass'] and tests['portable_margin3_b']['benchmark_pass']
independent=read(out/'single_bundle_rod_frames/independent_validation.json');solver=read(out/'single_bundle_rod_frames/report.json')
report={'status':'NATIVE_CURVE_BENCHMARK_PASS_SINGLE_MODEL_BUNDLE_UNRESOLVED','whole_hair_accepted':False,'benchmarks':tests,'single_bundle':independent,
 'single_bundle_shape':{'min_edge_ratio':solver['min_mesh_edge_ratio'],'max_edge_ratio':solver['max_mesh_edge_ratio'],'root_error_peak_m':solver['max_root_error_m'],'frame_240':next(x for x in solver['samples'] if x['frame']==240)},
 'independent_binding_math_tests':4,'video':str(out/'NativeHair_Collision_Benchmark_1080p_5s.mp4'),'video_coordinates_source':'portable_margin3_a','video_resolution':[1920,1080],'video_frames':150,'video_seconds':5.,'model_source_overwritten':False,'next_contact_phase':[217,220],
 'plugin':read(ROOT/'dist/animation_contact_package.json'),'notes':['Native curve self-contact not tested','Single bundle starts at frame200 with zero velocity','Source scalp/body open-region containment and CCD are not proven','Cached candidate preserves every unselected vertex and outside-range original geometry','A 1mm-margin packaged repeat failed and is retained; 3mm-margin independent repeats passed']}
(out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'status':report['status'],'failed_single_bundle_half_frames':independent['failed_samples'],'benchmark_independent_repeats':2,'candidate':independent['candidate']},ensure_ascii=False))
