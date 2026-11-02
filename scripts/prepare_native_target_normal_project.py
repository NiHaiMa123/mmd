import bpy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/jiggle_physics_20261031';src=base/'native_outside21';out=base/'native_outside22';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(src/'完整角色_Jiggle原版_原生表面约束_15秒.blend'),load_ui=False,use_scripts=False)
m=bpy.data.objects['东雪莲x达妮娅_素体'];md=next(md for md in m.modifiers if md.type=='SHRINKWRAP');md.wrap_method='TARGET_PROJECT'
for obj in bpy.data.objects:
 for modifier in obj.modifiers:
  if modifier.type=='MESH_CACHE':modifier.filepath=bpy.path.abspath(modifier.filepath)
path=out/'完整角色_Jiggle原版_原生表面约束_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path));report=json.loads((src/'configuration.json').read_text('utf8'));report.update(blend=str(path),surface_contact='Stock Blender Shrinkwrap: Target Normal Project / Outside');(out/'configuration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
