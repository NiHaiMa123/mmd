import sys,json
from pathlib import Path
from collections import Counter,defaultdict
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/white_bridal_shoes/checked/Daniya_WhiteBridal_FitChecked.blend'),load_ui=False,use_scripts=False)
target=next(o for o in ie.model_meshes() if not o.get('mmd_garment'))
profile=read_json(ROOT/'outputs/outfit_v09_final/20261024T114717Z_79592d70af/profile_snapshot.json');objects=ie.import_pmx(profile['source']['path']);source=ie.model_meshes(objects)[0]
report={}
for label,obj in [('target',target),('source',source)]:
 names={g.index:g.name for g in obj.vertex_groups};rows=[]
 for i,mat in enumerate(obj.data.materials):
  name=mat.mmd_material.name_j or mat.name
  if name not in ('Body','肌','顔'):continue
  faces=[f for f in obj.data.polygons if f.material_index==i];edges=Counter()
  positions={v.index:tuple(round(c,6) for c in v.co) for v in obj.data.vertices}
  for f in faces:
   for j,a in enumerate(f.vertices):edges[tuple(sorted((positions[a],positions[f.vertices[(j+1)%len(f.vertices)]])))]+=1
  boundary=[e for e,n in edges.items() if n==1 and min(p[2] for p in e)>1.28]
  used={j for f in faces for j in f.vertices}
  vertices=[{'id':v.index,'co':list(v.co),'groups':[(names[g.group],g.weight) for g in v.groups if g.weight>1e-5 and not names[g.group].startswith('mmd_')]} for v in obj.data.vertices if v.co.z>1.28 and v.index in used]
  rows.append({'material':name,'boundary_edges':boundary,'upper_vertices':vertices})
 report[label]=rows
 if label=='source':
  arm=next(o for o in objects if o.type=='ARMATURE');head=arm.data.bones['頭'];report['source_head_subtree']=[head.name]+[b.name for b in head.children_recursive]
  report['source_vertex_morph_properties']=[{prop.identifier:getattr(m,prop.identifier) for prop in m.bl_rna.properties if prop.identifier not in ('rna_type',) and prop.type in ('STRING','ENUM','BOOLEAN','INT','FLOAT')} for m in ie.mmd_root(arm).mmd_root.vertex_morphs]
write_json(ROOT/'outputs/keqing_head/inspection/neck_probe.json',report)
print('HEAD_NECK_PROBE',json.dumps({label:[{'material':r['material'],'boundary_edges':len(r['boundary_edges']),'upper_vertices':len(r['upper_vertices'])} for r in report[label]] for label in ('target','source')},ensure_ascii=False),flush=True)
