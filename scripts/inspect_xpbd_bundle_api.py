import bpy,json
from pathlib import Path
t=bpy.data.node_groups.new('InspectBundle','GeometryNodeTree');n=t.nodes.new('NodeCombineBundle');result={'properties':[(p.identifier,p.type) for p in n.bl_rna.properties]}
for name in ('bundle_items','items','inputs'):
 obj=getattr(n,name,None)
 if obj is not None:result[name]={'class':str(type(obj)),'methods':[x for x in dir(obj) if not x.startswith('_')]}
result['object_info_outputs']=[];obj=t.nodes.new('GeometryNodeObjectInfo');result['object_info_outputs']=[(s.name,s.identifier,s.bl_idname) for s in obj.outputs]
result['xpbd_inputs']=json.loads(Path('E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/hair_tests_v2/xpbd_available.json').read_text('utf8'))['types'][0]
print(json.dumps(result,ensure_ascii=False),flush=True)
