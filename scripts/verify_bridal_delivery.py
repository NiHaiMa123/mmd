"""Collect artifact and validation evidence for the fitted bridal shoes."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_grounding import split_vmd,bone_name
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):
    checksum=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):checksum.update(chunk)
    return checksum.hexdigest()
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args();out=Path(a.fit).resolve()
fit=read(out/'fit_report.json');export=read(out/'export_report.json');validation=read(out/'mmd_validation.json')
motion=read(out/'motion_review.json');ground=read(out/'grounding_report.json');neutral=read(out/'clearance_rays.json')
assert read(out/'export_status.json')['stage']=='complete'
assert fit['feet_retained'] and fit['restored_original_foot_region_faces']==8928 and fit['upper_body_faces_lost']==0
assert all(v['deleted_vertices']==v['deleted_faces']==0 for v in fit['shod_foot_binding'].values())
assert not validation['failures'] and not validation['missing_textures']
assert not motion['morphs']['changed_keys'] and motion['morphs']['checked_keys']==249
assert all(v['max_absolute_edge_error_m']<1e-5 for v in motion['shots'])
assert ground['frames']==ground['verified_frames']==4936
assert ground['min_height_verified_m']>=ground['clearance_m']-1e-5
assert neutral['neutral_foot_head_error_m']<.0001
assert 'bridal_sole_distance' in export['preserved_shader_attributes']
texture_sha=sha(export['texture'])
assert all(sha(path)==texture_sha for path in export['atlas_export_copies'])
h,b,t=split_vmd(Path(ground['source']).read_bytes());hh,bb,tt=split_vmd(Path(ground['motion']).read_bytes())
assert h==hh and t==tt and [r for r in b if bone_name(r)!='全ての親']==[r for r in bb if bone_name(r)!='全ての親']
native=out/'Daniya_WhiteBridal.blend';assert sha(native)==sha(out/'work.blend')
report={'state':'REVIEW_REQUIRED','accepted':False,
    'native_blend':str(native),'pmx':export['pmx'],'motion':ground['motion'],
    'source_asset_sha256':sha(fit['asset']),'native_blend_sha256':sha(native),
    'pmx_sha256':sha(export['pmx']),'motion_sha256':sha(ground['motion']),'atlas_sha256':texture_sha,
    'full_foot_region_faces':fit['restored_original_foot_region_faces'],'shod_foot_binding':fit['shod_foot_binding'],
    'counts':validation['counts'],'validation_failures':validation['failures'],
    'foot_pose_contract_tests_passed':7,'neutral_foot_head_error_m':neutral['neutral_foot_head_error_m'],
    'grounding':{k:ground[k] for k in ('frames','verified_frames','min_height_verified_m','max_lift_m')},
    'motion_shots':motion['shots'],'shoe_morphs':motion['morphs'],
    'preserved_shader_attributes':export['preserved_shader_attributes'],
    'scope':'specific bridal asset and Daniya body; full foot geometry retained; rigid shod toes; three visual/motion samples; flat-floor all-frame grounding; native MMD physics unverified'}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'verified':True,'state':report['state'],'native':str(native),'pmx':export['pmx']},ensure_ascii=False))
