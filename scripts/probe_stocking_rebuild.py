import sys,json
from pathlib import Path
from collections import Counter
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/work.blend'),load_ui=False,use_scripts=False)
body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];names={g.index:g.name for g in body.vertex_groups}
data={'materials':[],'private':{},'sleeve_bones':[]}
for mi,m in enumerate(body.data.materials):
    fs=[f for f in body.data.polygons if f.material_index==mi and f.center.z<1.08]
    if not fs:continue
    vs={i for f in fs for i in f.vertices}
    data['materials'].append({'name':m.name,'j':m.mmd_material.name_j,'faces':len(fs),'bounds':[[min(body.data.vertices[i].co[k] for i in vs),max(body.data.vertices[i].co[k] for i in vs)] for k in range(3)]})
for prefix in ('Pussy','Labia','Clit','Urethra','Anus'):
    vs=[v for v in body.data.vertices if sum(g.weight for g in v.groups if names[g.group].startswith(prefix))>.1]
    if vs:data['private'][prefix]={'count':len(vs),'bounds':[[min(v.co[k] for v in vs),max(v.co[k] for v in vs)] for k in range(3)]}
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
data['sleeve_bones']=[{'name':b.name,'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else ''} for b in arm.data.bones if b.name.startswith('袖_') and b.name.endswith('.L')]
data['stock_mat']=[{'name':m.name,'j':m.mmd_material.name_j,'images':[{'node':n.name,'path':n.image.filepath} for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]} for m in cloth.data.materials if m.mmd_material.name_j=='腿']
out=ROOT/'outputs/stockings_sleeves';out.mkdir(exist_ok=True,parents=True);(out/'probe.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(data,ensure_ascii=False),flush=True)
