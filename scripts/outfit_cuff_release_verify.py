"""Collect the cuff release evidence without granting visual acceptance."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.motion_grounding import split_vmd,bone_name


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    for name in ('release','previous-release','archive','out'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();directory=Path(args.release).resolve()
    result=read(directory/'release_e2e.json')['fit'];job=Path(result['job_dir'])
    old=read(args.previous_release)['fit'];profile=read(job/'profile_snapshot.json')
    validation=read(result['validation']);grounding=read(result['grounding_report'])
    qa=read(job/'motion/qa_report.json');shape=read(directory/'arm_shape_review.json')
    mesh=read(directory/'mesh_review.json')
    cuff=read(directory/'cuff_full_physics/report.json')
    baseline=read(directory/'baseline_full_physics/report.json')
    differences=[];private_assets=[]
    with zipfile.ZipFile(args.archive) as archive:
        for name in archive.namelist():
            if name.startswith('mmd_outfit/engine/'):source=ROOT/'src'/name.removeprefix('mmd_outfit/engine/')
            elif name=='mmd_outfit/README.md':source=ROOT/'addon/README.md'
            else:source=ROOT/'addon'/name
            if archive.read(name)!=source.read_bytes():differences.append(name)
            if name.endswith(('.blend','.pmx','.vmd')):private_assets.append(name)
    h,b,t=split_vmd(Path(grounding['source']).read_bytes())
    hh,bb,tt=split_vmd(Path(grounding['motion']).read_bytes())
    nonroot=lambda rows:[row for row in rows if bone_name(row)!='全ての親']
    helpers=cuff['helper_tracks']
    def physical_summary(data):
        return {'contact_matrix':data['setup']['contact_matrix'],
                'sampled_frames':[{k:row[k] for k in ('frame','crossing_pairs','by_material','deformation')} for row in data['motion']],
                'physics_subset':data['physics_subset'],'scope':data['scope']}
    report={'state':result['state'],'accepted':result['accepted'],'job_dir':str(job),
        'archive_sha256':digest(args.archive),'archive_source_differences':differences,'private_asset_files':private_assets,
        'input_hashes_match':{s:digest(profile[s]['path'])==profile[s]['sha256'] for s in ('source','target')},
        'counts':validation['counts'],'validation_failures':validation['failures'],'missing_textures':validation['missing_textures'],
        'cuff_physics':validation['cuff_physics'],'preserved_shoes':validation['preserved_shoes'],
        'shoe_reference_identical_to_previous':result['adaptations']['shoes']['reference_positions']==old['adaptations']['shoes']['reference_positions'],
        'grounded_vmd_identical_to_previous':Path(result['effective_motion']).read_bytes()==Path(old['effective_motion']).read_bytes(),
        'motion_nonroot_bytes_preserved':nonroot(b)==nonroot(bb),'motion_header_and_tail_preserved':h==hh and t==tt,
        'grounding':{k:grounding[k] for k in ('frames','verified_frames','min_height_verified_m','max_lift_m')},
        'arm_shape':shape,'mesh_comparison':mesh,
        'ordinary_qa':{'max_ratio':qa['motion']['max_ratio'],'deformation':qa['motion']['deformation']},
        'physics':{'baseline':physical_summary(baseline),'cuff':physical_summary(cuff),
                   'helper_tracked_frames':len(helpers),
                   'helper_max_local_step_m':max(row['max_local_step_m'] for row in helpers),
                   'helper_max_from_parent_rest_m':max(row['max_from_parent_rest_m'] for row in helpers),
                   'native_mmd_accepted':False}}
    assert result['ok'] and not result['accepted'] and profile['cuff_physics']
    assert not differences and not private_assets and all(report['input_hashes_match'].values())
    assert not validation['failures'] and not validation['missing_textures'] and not validation['cuff_physics']['failures']
    assert shape['passed'] and mesh['passed'] and mesh['changed_weight_vertices']==validation['cuff_physics']['weighted_vertices']
    assert report['shoe_reference_identical_to_previous'] and report['grounded_vmd_identical_to_previous']
    assert report['motion_nonroot_bytes_preserved'] and report['motion_header_and_tail_preserved']
    assert grounding['frames']==grounding['verified_frames'] and grounding['min_height_verified_m']>=grounding['clearance_m']-1e-5
    assert not validation['preserved_shoes']['vertex_morphs']['changed_keys']
    assert len(helpers)==256
    for data in (cuff,baseline):
        assert data['physics'] and data['physics_subset'] is None
        matrix=data['setup']['contact_matrix']
        assert matrix['false_positive_layer_pairs']==matrix['false_negative_layer_pairs']==0
        assert all(row['deformation']['large_edges']==row['deformation']['severe_edges']==0 for row in data['motion'])
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({'verified':True,'sha256':report['archive_sha256'],'job_dir':str(job),'accepted':False}))


if __name__=='__main__':main()
