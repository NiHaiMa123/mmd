"""Ship experimental sources separately; never replace the stable plugin ZIP."""
import hashlib,json,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];skill=ROOT/'skills/repair-animation-contact';dist=ROOT/'dist';dist.mkdir(exist_ok=True);snapshot=skill/'assets/contact-experiments-20261030.zip'
manifest=dict(status='EXPERIMENTAL_SOURCE_SNAPSHOT_NOT_STABLE_RELEASE',stable_plugin_version_unchanged='0.1.6',entry='Extract; add addon/ to Blender Python path; use mapped inputs described in the skill reference',dependencies=['Blender Python + NumPy','Optional Windows PPF native runtime at tools/ppf/native, acquired separately'],full_15_second_hair_accepted=False,ui_auto_enabled=False)
with zipfile.ZipFile(snapshot,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for file in sorted((ROOT/'addon/animation_contact_tools').glob('*.py')):z.write(file,'addon/animation_contact_tools/'+file.name)
 for name in ('solve_ppf_hair_volume.py','condition_ppf_collision_triangles.py','reduce_ppf_body_keys.py','capture_ppf_prefix.py'):z.write(ROOT/'scripts'/name,'scripts/'+name)
 z.writestr('experiment.json',json.dumps(manifest,indent=2))
target=dist/snapshot.name;shutil.copyfile(snapshot,target);skill_zip=dist/'repair-animation-contact-skill-experimental-20261030.zip'
with zipfile.ZipFile(skill_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for file in sorted(skill.rglob('*')):
  if file.is_file() and '__pycache__' not in file.parts:z.write(file,'repair-animation-contact/'+file.relative_to(skill).as_posix())
receipt=dict(snapshot=str(target),snapshot_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),skill=str(skill_zip),stable_plugin_replaced=False,experimental=True)
(dist/'contact_experiment_snapshot.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))
