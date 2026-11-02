import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.heeled_foot import bind_shod_forefoot
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();ie=engine('import_export');ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(out/'work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
report=read_json(out/'fit_report.json');report['shod_foot_binding']={obj.name:bind_shod_forefoot(obj,arm) for obj in ie.model_meshes() if not obj.get('external_shoe')}
write_json(out/'fit_report.json',report);bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'))
print('SHOD_FOREFOOT_BOUND',report['shod_foot_binding'],flush=True)
