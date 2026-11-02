"""Recalculate the hidden closed target's normals with Blender's stock mesh tool."""
import bpy,bmesh,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031';src=base/'native_outside19';out=base/'native_outside20';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_Jiggle原版_原生表面约束_15秒.blend'),load_ui=False,use_scripts=False)
body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];before=[tuple(p.vertices) for p in body.data.polygons];bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(body.data);bm.free();body.data.update()
after=[tuple(p.vertices) for p in body.data.polygons];changed=sum(x!=y for x,y in zip(before,after))
for obj in bpy.data.objects:
 for md in obj.modifiers:
  if md.type=='MESH_CACHE':md.filepath=bpy.path.abspath(md.filepath)
path=out/'完整角色_Jiggle原版_原生表面约束_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));config=json.loads((src/'configuration.json').read_text('utf8'));config.update(blend=str(path),normals_recalculated_by='Blender bmesh.ops.recalc_face_normals',target_faces_reoriented=changed)
(out/'configuration.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf8');print('TARGET_NORMALS_REORIENTED',changed,flush=True)
