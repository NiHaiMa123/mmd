"""Package the exact versioned runtime, profile, initial calibration and commands."""
import argparse,json,zipfile,hashlib,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args();root=Path(__file__).resolve().parents[1];out=Path(a.delivery);pub=json.loads((out/'cache_publication.json').read_text('utf8'));run=Path(pub['run']);fingerprint=json.loads((run/'input_fingerprint.json').read_text('utf8'));src=Path(pub['input']);manifest=json.loads((src/'export_complete.json').read_text('utf8'));bundle=out/'整头避碰算法_源码参数与初态_20261030.zip'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
for name,digest in fingerprint['inputs']['algorithm'].items():assert sha(root/'tools/contact_stack/mmd_hair_dynamics'/name)==digest,name
scripts=['export_full_hair_dynamics','scan_full_hair_roots_gpu','plan_full_hair_contact_windows','plan_full_hair_arm_route','solve_full_hair_root_feedback','prepare_full_hair_route_skin','run_full_hair_dynamics','publish_full_hair_cache','follow_full_hair_publication','assemble_full_hair_showcase','audit_full_hair_showcase','merge_full_hair_native_audits','check_full_hair_checkpoint_replay','verify_full_hair_source_preservation','render_full_hair_showcase','encode_full_hair_showcase','fork_full_hair_verified_prefix','upgrade_full_hair_contact_state','audit_full_hair_arm_route_body'];files=[]
for folder in ['addon/animation_contact_tools','addon/mmd_outfit','src','tools/contact_stack/mmd_hair_dynamics']:
 files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ['.py','.json','.txt','.md'])
files.extend(root/'scripts'/(name+'.py') for name in scripts);files.extend([root/'tools/contact_stack/requirements-hair-dynamics.txt',root/'docs/FULL_HEAD_REPRO_MMD15_2026-10-30.md']);entries=[]
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for path in sorted(set(files)):
  relative=path.relative_to(root).as_posix();z.write(path,relative);entries.append(dict(path=relative,sha256=sha(path)))
 for name,path in [('calibration/InitialHairRest.npz',manifest['initial_file']),('calibration/rig_profile.json',manifest['rig_profile']),('calibration/solver_config.json',run/'config.json'),('calibration/input_fingerprint.json',run/'input_fingerprint.json')]:z.write(path,name);entries.append(dict(path=name,sha256=sha(path)))
 z.writestr('bundle_manifest.json',json.dumps(dict(algorithm_fingerprint=pub['fingerprint'],files=entries,scope='same-character calibrated initial state, automated arm routes, full-head dynamics plus geometric contact projection; 15-second validation does not certify the whole longer film'),ensure_ascii=False,indent=2))
shutil.copy2(root/'docs/FULL_HEAD_REPRO_MMD15_2026-10-30.md',out/'算法与复现说明.md');shutil.copy2(run/'config.json',out/'solver_config.json');report=dict(bundle=str(bundle),bytes=bundle.stat().st_size,sha256=sha(bundle),algorithm_fingerprint=pub['fingerprint'],source_files=len(entries));(out/'repro_bundle_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('REPRO_BUNDLE_BUILT',json.dumps(report,ensure_ascii=False),flush=True)
