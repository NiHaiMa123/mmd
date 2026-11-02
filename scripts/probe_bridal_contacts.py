import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/white_bridal_shoes/final/Daniya_WhiteBridal_Clean.blend'),load_ui=False,use_scripts=False)
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));cloth=bpy.data.objects['Cloth']
faces=[f for f in body.data.polygons if (body.data.materials[f.material_index].mmd_material.name_j or body.data.materials[f.material_index].name) in {'Body','Nails'} and min(body.data.vertices[i].co.z for i in f.vertices)<.1953568]
ids=sorted({i for f in faces for i in f.vertices});offset=len(cloth.data.vertices)-len(ids)
print('MAPPING',len(faces),len(ids),offset, max((body.data.vertices[i].co-cloth.data.vertices[offset+j].co).length for j,i in enumerate(ids)),flush=True)
data={}
for obj in bpy.data.objects:
 if not obj.get('external_shoe') or not obj.name.endswith('.L'):continue
 mesh=obj.data;points=[obj.matrix_world@v.co for v in mesh.vertices];mesh.calc_loop_triangles()
 groups={}
 for tri in mesh.loop_triangles:
  key=mesh.materials[tri.material_index].name;row=groups.setdefault(key,{'triangles':0,'min':[1e6]*3,'max':[-1e6]*3,'normals':[]})
  row['triangles']+=1;p=[points[i] for i in tri.vertices];n=(p[1]-p[0]).cross(p[2]-p[0]).normalized();center=sum(p,Vector())/3
  for k in range(3):row['min'][k]=min(row['min'][k],center[k]);row['max'][k]=max(row['max'][k],center[k])
  if len(row['normals'])<5:row['normals'].append([list(center),list(n)])
 data[obj.name]=groups
print('SHOE_SURFACES',json.dumps(data,ensure_ascii=False),flush=True)
(ROOT/'outputs/white_bridal_shoes/contact_probe.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
