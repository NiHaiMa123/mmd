"""Package only the standalone addon and bundle it into its portable skill."""
import ast,json,zipfile,shutil,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];addon=root/'addon/animation_contact_tools';dist=root/'dist';dist.mkdir(exist_ok=True)
info=next(ast.literal_eval(n.value) for n in ast.parse((addon/'__init__.py').read_text('utf8')).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets));version=tuple(info['version'])
target=dist/('animation_contact_tools-'+'.'.join(map(str,version))+'.zip')
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(addon.glob('*.py')):z.write(p,'animation_contact_tools/'+p.name)
skill=root/'skills/repair-animation-contact';shutil.copyfile(target,skill/'assets/animation_contact_tools.zip')
profile=json.loads((root/'outputs/portable_contact_contract/rig_profile.json').read_text('utf8'));profile.update(rotation_limit_degrees=25,verification_step=.25,preserve_wrist_orientation=True)
(skill/'references/generic-profile.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
skill_zip=dist/'repair-animation-contact-skill.zip'
with zipfile.ZipFile(skill_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in sorted(skill.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:z.write(p,'repair-animation-contact/'+p.relative_to(skill).as_posix())
receipt={'plugin':str(target),'plugin_version':version,'plugin_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'skill':str(skill_zip),'plugin_python_files':len(list(addon.glob('*.py')))}
(dist/'animation_contact_package.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps(receipt))
