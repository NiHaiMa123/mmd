"""Use only original skin triangles as the stock Shrinkwrap target."""
import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex';src=base/'jiggle_physics_20261031/native_outside19';out=base/'jiggle_physics_20261031/native_outside21';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_Jiggle原版_原生表面约束_15秒.blend'),use_scripts=False,load_ui=False)
body=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部'];data=base/'fullhair_repro_20261030/input_body_aware';faces=np.load(data/'body_faces.npy');real=np.load(data/'real_body_faces.npy').astype(bool);vertices=np.array([v.co[:] for v in body.data.vertices]);mesh=bpy.data.meshes.new('NativeOutside_仅真实皮肤_无虚拟封口');mesh.from_pydata(vertices.tolist(),[],faces[real].tolist());mesh.update();body.data=mesh
for obj in bpy.data.objects:
 for md in obj.modifiers:
  if md.type=='MESH_CACHE':md.filepath=bpy.path.abspath(md.filepath)
bpy.context.scene.frame_set(1);bpy.context.view_layer.update();path=out/'完整角色_Jiggle原版_原生表面约束_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));report=json.loads((src/'configuration.json').read_text('utf8'));report.update(blend=str(path),target_real_skin_triangles=int(real.sum()),target_synthetic_cap_triangles=0,removed_synthetic_caps=int((~real).sum()),target_vertices=len(vertices))
(out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
