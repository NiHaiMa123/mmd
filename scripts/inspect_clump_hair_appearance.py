"""Read-only material, ray visibility and evaluated normal comparison."""
import json,sys,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
base=ROOT.parent/'work/headswap_xl_codex';out=base/'standard_proxy_20261031/clumps07/appearance_review';out.mkdir(parents=True,exist_ok=True)
engine('import_export').ensure_mmd_tools()
def value(v):
    try:return list(v)
    except TypeError:return v
def record(obj):
    result=dict(object=obj.name,world=[list(r) for r in obj.matrix_world],ray_visibility={p:getattr(obj,p) for p in ['visible_camera','visible_diffuse','visible_glossy','visible_transmission','visible_volume_scatter','visible_shadow']},materials=[dict(index=i,link=slot.link,name=slot.material.name if slot.material else None) for i,slot in enumerate(obj.material_slots)],modifiers=[dict(type=md.type,name=md.name) for md in obj.modifiers])
    mats={}
    for slot in obj.material_slots:
        mat=slot.material
        if mat is None or mat.name in mats:continue
        nodes=[]
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                inputs={x.name:value(x.default_value) for x in n.inputs if hasattr(x,'default_value') and not x.is_linked and x.type in ('VALUE','RGBA','VECTOR','INT','BOOLEAN','STRING')}
                nodes.append(dict(name=n.name,type=n.bl_idname,inputs=inputs,image=n.image.filepath if n.type=='TEX_IMAGE' and n.image else None,attribute=getattr(n,'attribute_name',None)))
        mats[mat.name]=dict(nodes=nodes,links=[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links] if mat.node_tree else [])
    result['material_nodes']=mats
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    try:
        ids=np.array([x.value for x in me.attributes['SourceVertexID'].data],np.int32) if me.attributes.get('SourceVertexID') else np.arange(len(me.vertices))
        normals=np.zeros((68272,3));counts=np.zeros(68272);co=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3);world=np.array(ev.matrix_world);co=co@world[:3,:3].T+world[:3,3]
        normalmatrix=np.linalg.inv(world[:3,:3]).T
        for loop,n in zip(me.loops,me.corner_normals):
            k=ids[loop.vertex_index];vec=normalmatrix@np.array(n.vector);vec/=max(np.linalg.norm(vec),1e-20);normals[k]+=vec;counts[k]+=1
        normals/=np.maximum(counts,1)[:,None];normals/=np.maximum(np.linalg.norm(normals,axis=1),1e-20)[:,None]
        result.update(vertices=len(me.vertices),has_custom_normals=me.has_custom_normals,attributes=[dict(name=x.name,domain=x.domain,type=x.data_type) for x in me.attributes],uv_layers=[dict(name=x.name,active_render=x.active_render) for x in me.uv_layers])
        return result,normals,ids,co
    finally:ev.to_mesh_clear()
rows={};normaldata={}
sources=dict(old_normal=base/'animation15_20261028/东雪莲_固定镜头_15秒.blend',prepared_source=base/'jiggle_physics_20261031/candidate10/完整角色_Jiggle配置_未烘焙.blend',split_candidate=base/'standard_proxy_20261031/clumps07/完整角色_原生分束代理_连续物理待验收.blend')
for label,path in sources.items():
    bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False,load_ui=False);bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    actor=bpy.data.objects['东雪莲x达妮娅_素体'];obj=bpy.data.objects[bpy.context.scene['HairDisplayObject']] if label=='split_candidate' else actor
    result,normals,ids,co=record(obj);rows[label]=result;normaldata[label]=normals
    if label=='split_candidate':rows['masked_actor_ray_visibility']={p:getattr(actor,p) for p in ['visible_camera','visible_diffuse','visible_glossy','visible_transmission','visible_volume_scatter','visible_shadow']}
hairids=np.load(base/'fullhair_repro_20261030/input_body_aware/hair_ids.npy')
angles=np.degrees(np.arccos(np.clip(np.sum(normaldata['prepared_source'][hairids]*normaldata['split_candidate'][hairids],axis=1),-1,1)))
rows['normal_difference_degrees']=dict(p50=float(np.median(angles)),p95=float(np.quantile(angles,.95)),max=float(angles.max()))
(out/'appearance_inspection.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8');print('APPEARANCE_INSPECTION',json.dumps({k:dict(object=v['object'],ray_visibility=v['ray_visibility']) for k,v in rows.items() if isinstance(v,dict) and 'object' in v},ensure_ascii=False),flush=True);print('NORMAL_DIFF',rows['normal_difference_degrees'],flush=True)
