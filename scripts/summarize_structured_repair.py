"""Summarize actual repair, cache and video checks without all-motion claims."""
import json,argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args();out=Path(a.fit).resolve()
def read(name):return json.loads((out/name).read_text(encoding='utf-8'))
validation=read('repair_validation.json');cache=read('cache_reload_report.json');video=read('video_report.json');setup=read('setup.json');sim=read('simulation_report.json');folds=read('fold_comparison.json')
assert all(validation['protected_meshes'].values())
assert max(validation['motion_coordinate_error_m'].values())<1e-5
assert max(row['maximum_absolute_edge_change_m'] for row in validation['anchors'].values())<.0001
assert all(row['max']>.001 for row in validation['visual_cloth_motion_m'].values())
assert cache['cache_baked_on_reload'] and all(row['bounds_error_m']<1e-5 for row in cache['frames'].values())
assert float(video['format']['duration'])==15 and any(s['codec_type']=='audio' for s in video['streams'])
report={'status':'REPAIRED_PREVIEW_READY','video':str(out/'Cynical_Cloth_15s_preview.mp4'),'blend':str(out/'Cynical_Cloth_15s.blend'),'scope':'structured skirt and sleeve cloth; first 15 seconds; Blender only','protected_original_meshes':len(validation['protected_meshes']),'character_and_morph_coordinates_unchanged':True,'sampled_body_motion_unchanged':True,'fully_fixed_edges':32,'sampled_max_fixed_edge_error_mm':max(row['maximum_absolute_edge_change_m'] for row in validation['anchors'].values())*1000,'cloth_motion_retained':True,'cloth_mode':setup['cloth']['method'],'preroll_frames':setup['preroll_frames'],'visible_frames':setup['frames'],'cache_frames':sim['requested_frames'],'preview_seconds':15,'preview_fps':15,'cache_reload_matched':True,'fold_comparison':folds,'limits':['Natural folds and some local overlap remain; no all-frame cloth-contact guarantee.','Shape-preserving blend of real cloth and attached reference, not unconstrained free cloth.','Hair secondary physics and PMX export are outside this repair.','640x360, 15-fps review render.']}
(out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('STRUCTURED_REPAIR_ACCEPTANCE',report['status'],report['sampled_max_fixed_edge_error_mm'])
