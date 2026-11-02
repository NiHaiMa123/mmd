import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/stockings_sleeves/v15/work.blend'),load_ui=False,use_scripts=False)
for m in bpy.data.objects['Cloth'].data.materials:
    if m.mmd_material.name_j not in {'新規','服+jinshu'}:continue
    print('MATERIAL',m.name,'alpha',m.mmd_material.alpha,'diffuse',tuple(m.diffuse_color),flush=True)
    for node in m.node_tree.nodes:
        if node.type=='GROUP':print('GROUP',node.name,[(s.name,str(s.default_value),s.is_linked) for s in node.inputs if 'alpha' in s.name.lower()],flush=True)
