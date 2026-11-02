"""Collect verifiable release facts; does not grant visual acceptance."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_grounding import split_vmd,bone_name


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    for n in ('job','previous-job','archive','shape-report','sleeve-report','previous-sleeve-report','physics-report','out'):
        p.add_argument('--'+n,required=True)
    a=p.parse_args();job=Path(a.job).resolve();r=read(job/'result.json');profile=read(job/'profile_snapshot.json')
    old=read(Path(a.previous_job)/'result.json');validation=read(job/'validation.json')
    grounding=read(r['grounding_report']);qa=read(job/'motion/qa_report.json')
    shape=read(a.shape_report);physics=read(a.physics_report)
    with zipfile.ZipFile(a.archive) as z:
        differences=[];experimental=[]
        for name in z.namelist():
            if name.startswith('mmd_outfit/engine/'):path=ROOT/'src'/name.removeprefix('mmd_outfit/engine/')
            elif name=='mmd_outfit/README.md':path=ROOT/'addon/README.md'
            else:path=ROOT/'addon'/name
            if z.read(name)!=path.read_bytes():differences.append(name)
            if 'experimental' in name:experimental.append(name)
    h,b,t=split_vmd(Path(grounding['source']).read_bytes())
    hh,bb,tt=split_vmd(Path(grounding['motion']).read_bytes())
    non_root_same=[v for v in b if bone_name(v)!='全ての親']==[v for v in bb if bone_name(v)!='全ての親']
    sleeve=read(a.sleeve_report);before=read(a.previous_sleeve_report)
    rows={row['frame']:row['crossing_pairs'] for row in sleeve['motion']}
    old_rows={row['frame']:row['crossing_pairs'] for row in before['motion']}
    report={'state':r['state'],'accepted':r['accepted'],'archive_sha256':digest(a.archive),
            'archive_source_differences':differences,'archive_experimental_files':experimental,
            'input_hashes':{s:{'sha256':digest(profile[s]['path']),'matches_profile':digest(profile[s]['path'])==profile[s]['sha256']}
                            for s in ('source','target')},
            'validation_failures':validation['failures'],'missing_textures':validation['missing_textures'],
            'counts':validation['counts'],'preserved_shoes':validation['preserved_shoes'],
            'shoe_reference_identical_to_previous':r['adaptations']['shoes']['reference_positions']==old['adaptations']['shoes']['reference_positions'],
            'grounded_vmd_identical_to_previous':Path(r['effective_motion']).read_bytes()==Path(old['effective_motion']).read_bytes(),
            'motion_non_root_bytes_preserved':non_root_same,'motion_header_and_tail_preserved':h==hh and t==tt,
            'grounding':{k:grounding[k] for k in ('frames','verified_frames','min_height_verified_m','max_lift_m')},
            'arm_shape':shape,'sleeve_crossings':{'before':old_rows,'after':rows,'scope':sleeve['scope']},
            'ordinary_qa':{'max_ratio':qa['motion']['max_ratio'],'deformation':qa['motion']['deformation']},
            'physics':{'contact_matrix':physics['setup']['contact_matrix'],'deformation':physics['deformation'],
                       'dynamic_near_gap_false_positive_max':physics['dynamic_near_gap_false_positive_max'],
                       'dynamic_near_gap_false_negative_max':physics['dynamic_near_gap_false_negative_max'],
                       'max_ratio':physics['max_ratio'],'frames':physics['frames'],'scope':physics['scope']}}
    assert r['ok'] and not r['accepted'] and not differences and not experimental
    assert not validation['failures'] and not validation['missing_textures']
    assert all(v['matches_profile'] for v in report['input_hashes'].values())
    assert shape['passed'] and report['shoe_reference_identical_to_previous']
    assert report['grounded_vmd_identical_to_previous'] and non_root_same and h==hh and t==tt
    assert grounding['frames']==grounding['verified_frames'] and grounding['min_height_verified_m']>=grounding['clearance_m']-1e-5
    assert not validation['preserved_shoes']['vertex_morphs']['changed_keys']
    Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    print(json.dumps({'verified':True,'archive_sha256':report['archive_sha256'],'state':r['state'],'accepted':r['accepted']}))


if __name__=='__main__':main()
