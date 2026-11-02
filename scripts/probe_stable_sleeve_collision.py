import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/sleeve_fixed/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);bpy.context.scene.frame_set(1);report={}
for name in ('ClothSimulationSurface','CachedSkirtSleeveCollider','StableSleeveSimulationSurface'):
 obj=bpy.data.objects[name];ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();attr=mesh.attributes.get('StableSleeveMask');report[name]={'vertices':len(mesh.vertices),'faces':len(mesh.polygons),'sleeve_mask_points':sum(d.value for d in attr.data) if attr else None,'bounds':[[min(v.co[k] for v in mesh.vertices),max(v.co[k] for v in mesh.vertices)] for k in range(3)]};ev.to_mesh_clear()
obj=bpy.data.objects['StableSleeveSimulationSurface'];pin=obj.vertex_groups['ClothPins'].index;report['new_pin_weights']={'full':sum(any(g.group==pin and g.weight>.999 for g in v.groups) for v in obj.data.vertices),'max':max((g.weight for v in obj.data.vertices for g in v.groups if g.group==pin),default=0)};print('SLEEVE_COLLISION_GEOMETRY',json.dumps(report),flush=True)
