import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();out=ROOT/'outputs/keqing_head/final'
bpy.ops.wm.open_mainfile(filepath=str(out/'work.blend'),load_ui=False,use_scripts=False)
body=next(o for o in ie.model_meshes() if not o.get('mmd_garment'));r=json.loads((out/'head_swap_report.json').read_text(encoding='utf8'))
body.data.update();bridge=list(body.data.polygons)[-r['neck_bridge']['bridge_faces']:];center=Vector((0,.04,1.33))
print('BRIDGE_NORMALS',[(f.index,round(f.normal.dot(Vector((f.center.x-center.x,f.center.y-center.y,0))),6)) for f in bridge],flush=True)
skin=next(m for m in body.data.materials if m.mmd_material.name_j=='肌')
print('SKIN',skin.name,skin.use_backface_culling,skin.mmd_material.is_double_sided,flush=True)
for node in skin.node_tree.nodes:
 print('NODE',node.name,node.type,[(s.name,len(s.links)) for s in node.inputs if s.name in ('Alpha','Surface','Color','Base Color')],flush=True)
 if node.type=='TEX_IMAGE' and node.image:
  im=node.image;print('IMAGE',im.name,im.filepath,list(im.size),flush=True)
  import numpy as np
  pixels=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(pixels);pixels=pixels.reshape(-1,4)
  print('IMAGE_ALPHA',float(pixels[:,3].min()),float(pixels[:,3].max()),flush=True)
  uv=body.data.uv_layers.active;rows=[]
  for f in bridge[:12]:
   for li in f.loop_indices:
    p=uv.data[li].uv;x=int((p.x%1)*(im.size[0]-1));y=int((p.y%1)*(im.size[1]-1));rows.append([list(p),pixels[y*im.size[0]+x].tolist()])
  print('BRIDGE_TEXELS',rows,flush=True)
