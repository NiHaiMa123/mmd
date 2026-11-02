import bpy,sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
out=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input';r=json.loads((out/'export_complete.json').read_text('utf8'));p=json.loads(Path(r['rig_profile']).read_text('utf8'));engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['source_blend'],load_ui=False,use_scripts=False);m=bpy.data.objects[p['mesh']];roles=list(p['bone_roles']);gn={g.index:g.name for g in m.vertex_groups};bone_role={name:i for i,role in enumerate(roles) for name in p['bone_roles'][role]};skin=np.load(out/'skin_ids.npy');weight=np.zeros((len(skin),len(roles)))
for j,i in enumerate(skin):
 for g in m.data.vertices[i].groups:
  role=bone_role.get(gn[g.group])
  if role is not None:weight[j,role]+=g.weight
faces=np.load(out/'body_faces.npy');label=weight[faces].sum(1).argmax(1);np.save(out/'body_face_role.npy',label.astype(np.int32));(out/'body_role_names.json').write_text(json.dumps(roles,ensure_ascii=False),encoding='utf8');print('FACE_ROLES_EXPORTED',roles,flush=True)
