import sys
from pathlib import Path
from collections import Counter
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from bridal_multiview_review import snapshot
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/stockings_sleeves/v6/work.blend'),load_ui=False,use_scripts=False)
obj=bpy.data.objects['Cloth'];print('BASE_MIN_Z',min(v.co.z for v in obj.data.vertices),'LOW_FACES',Counter(obj.data.materials[f.material_index].mmd_material.name_j for f in obj.data.polygons if max(obj.data.vertices[i].co.z for i in f.vertices)<.27),flush=True)
row=snapshot(obj,'R',.27);me=row[0].data;print('SNAPSHOT_COUNTS',len(me.vertices),len(me.polygons),'ATTR_KEYS',list(me.attributes.keys()),flush=True)
if len(me.vertices):print('REST_RANGE',[[min(d.vector[k] for d in me.attributes['ReviewRestPosition'].data),max(d.vector[k] for d in me.attributes['ReviewRestPosition'].data)] for k in range(3)],'CO_RANGE',[[min(v.co[k] for v in me.vertices),max(v.co[k] for v in me.vertices)] for k in range(3)],flush=True)
