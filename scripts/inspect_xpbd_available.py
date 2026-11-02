import json
from pathlib import Path
import bpy
out=Path('E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/hair_tests_v2');out.mkdir(exist_ok=True)
types=[n for n in dir(bpy.types) if any(s.lower() in n.lower() for s in ('xpbd','constraint','collision')) and n.startswith('GeometryNode')]
tree=bpy.data.node_groups.new('InspectXPBD','GeometryNodeTree');nodes=[]
for name in types:
 try:
  node=tree.nodes.new(name);props={p.identifier:str(getattr(node,p.identifier,None)) for p in node.bl_rna.properties if p.identifier not in ('rna_type','inputs','outputs','id_data','internal_links','color','location','dimensions','parent','select')};nodes.append({'type':name,'inputs':[(s.name,s.identifier,s.bl_socket_idname) for s in node.inputs],'outputs':[(s.name,s.identifier,s.bl_socket_idname) for s in node.outputs],'properties':props})
 except Exception as e:nodes.append({'type':name,'error':str(e)})
assets=[]
for file in Path('D:/software/blender/5.2.1/5.2/datafiles/assets/nodes').rglob('*.blend'):
 try:
  with bpy.data.libraries.load(str(file),link=False) as (source,dest):assets.append({'path':str(file),'node_groups':list(source.node_groups)})
 except Exception as e:assets.append({'path':str(file),'error':str(e)})
(out/'xpbd_available.json').write_text(json.dumps({'types':nodes,'assets':assets},ensure_ascii=False,indent=2),encoding='utf8');print('XPBD_TYPES',types,flush=True);print('XPBD_ASSETS',[a for a in assets if any('Dynamic' in n or 'XPBD' in n or 'Constraint' in n for n in a.get('node_groups',[]))],flush=True)
