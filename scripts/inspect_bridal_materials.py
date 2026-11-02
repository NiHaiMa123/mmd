import sys,json,bpy
from pathlib import Path
p=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(p/'work.blend'),load_ui=False,use_scripts=False)
obj=bpy.data.objects['Bridal_high heel shoe 3d model.L']
rows=[]
for mat in obj.data.materials:
    nodes=[]
    for node in mat.node_tree.nodes:
        row={'type':node.type,'name':node.name}
        if node.type=='ATTRIBUTE':row['attribute']=node.attribute_name
        if node.type=='TEX_COORD':row['object']=getattr(node.object,'name',None)
        if node.type=='GROUP':row['group']=node.node_tree.name
        row['connections']={socket.name:[link.from_node.type+':'+link.from_socket.name for link in socket.links] for socket in node.inputs if socket.is_linked}
        if node.type=='BSDF_PRINCIPLED':row['base_color']=list(node.inputs['Base Color'].default_value)
        nodes.append(row)
    rows.append({'material':mat.name,'nodes':nodes})
(p/'material_nodes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(rows,ensure_ascii=True),flush=True)
