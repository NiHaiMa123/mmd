"""Separate old cloth-carrier deformation from ordinary skeletal skinning."""
import argparse,sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);cloth=bpy.data.objects['Cloth'];disabled=[]
for mod in cloth.modifiers:
    enabled=mod.type in ('ARMATURE','SUBSURF');mod.show_viewport=enabled;mod.show_render=enabled
    if not enabled:disabled.append(mod.name)
    if mod.type=='SUBSURF':mod.levels=2;mod.render_levels=2
scene=bpy.context.scene;scene.frame_set(325);scene.frame_start=325;scene.frame_end=325
for polygon in bpy.data.objects['ContinuousExteriorNylon'].data.polygons:polygon.use_smooth=True
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_SkinningOnly325.blend'),compress=True);(out/'ablation.json').write_text(json.dumps({'disabled':disabled,'scope':'diagnostic; no cloth dynamics'},indent=2),encoding='utf8')
