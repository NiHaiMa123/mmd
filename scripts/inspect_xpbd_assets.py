import json
from pathlib import Path
import bpy
out=Path('E:/project/mmd/work/headswap_xl_codex/contact_repair_20261028/hair_tests_v2');asset='D:/software/blender/5.2.1/5.2/datafiles/assets/nodes/geometry_nodes_dynamics_assets.blend'
with bpy.data.libraries.load(asset,link=False) as (source,dest):dest.node_groups=list(source.node_groups)
report=[]
for name in ('Hair Dynamics','Cloth Dynamics (Experimental)','Collider','Pin Positions','Edge Length Constraint','XPBD Simulation','Set Geometry Tags','XPBD Solver'):
 tree=bpy.data.node_groups[name];interface=[]
 for item in tree.interface.items_tree:
  if item.item_type=='SOCKET':interface.append({'name':item.name,'identifier':item.identifier,'direction':item.in_out,'type':item.socket_type,'default':str(getattr(item,'default_value','')),'description':item.description})
 nodes=[]
 for node in tree.nodes:
  nodes.append({'name':node.name,'label':node.label,'type':node.bl_idname,'group':node.node_tree.name if node.type=='GROUP' else None,'inputs':[(s.name,s.identifier,str(getattr(s,'default_value',''))) for s in node.inputs],'outputs':[(s.name,s.identifier) for s in node.outputs]})
 links=[(l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in tree.links]
 report.append({'name':name,'interface':interface,'nodes':nodes,'links':links});print('XPBD_INTERFACE',name,interface,flush=True)
(out/'xpbd_asset_graphs.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
