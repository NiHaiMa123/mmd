import sys,json
from pathlib import Path
from collections import defaultdict
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools()
folder=ROOT/'outputs/white_bridal_shoes/checked'
bpy.ops.wm.open_mainfile(filepath=str(folder/'work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');arm.hide_set(False);bpy.context.view_layer.objects.active=arm;arm.select_set(True)
bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/white_bridal_shoes/final/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
bpy.context.scene.frame_set(256);bpy.context.view_layer.update()
report=json.loads((folder/'residual_probe/report.json').read_text(encoding='utf8'))
for key,row in report['sides'].items():
 if not key.startswith('256'):continue
 groups=defaultdict(list)
 for seg in row['segments']:groups[(seg['layer'],seg['shoe'])].extend(seg['points'])
 for (layer,shoe),points in groups.items():
  side=key[-1];bone='ひざD.'+side if 'Sphere' in shoe or '大蝴蝶结' in shoe else '足首D.'+side
  transform=arm.pose.bones[bone].matrix@arm.data.bones[bone].matrix_local.inverted();inverse=transform.inverted()
  local=[inverse@Vector(p) for p in points]
  obj=bpy.data.objects[layer];tree=KDTree(len(obj.data.vertices))
  for v in obj.data.vertices:tree.insert(v.co,v.index)
  tree.balance();ids=sorted({tree.find(p)[1] for p in local})
  print('CONTACT_REGION',key,layer,shoe,bone,'range',[(min(p[k] for p in local),max(p[k] for p in local)) for k in range(3)],'weights',[(i,list(obj.data.vertices[i].co),[(obj.vertex_groups[g.group].name,round(g.weight,4)) for g in obj.data.vertices[i].groups if not obj.vertex_groups[g.group].name.startswith('mmd_')]) for i in ids[:8]],flush=True)
  print('FACE_MATERIALS',[(i,sorted({obj.data.materials[f.material_index].name for f in obj.data.polygons if i in f.vertices})) for i in ids[:8]],flush=True)
  exact=sorted({i for seg in row['segments'] for i in seg['layer_vertices']})
  print('EXACT_VERTICES',[(i,list(obj.data.vertices[i].co),[(obj.vertex_groups[g.group].name,round(g.weight,5)) for g in obj.data.vertices[i].groups if not obj.vertex_groups[g.group].name.startswith('mmd_')]) for i in exact],flush=True)
