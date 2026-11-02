"""Build an independent clean garment-contact base without broad projections."""
import argparse,json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];lining=bpy.data.objects['SleeveLining'];stock=bpy.data.objects['Stockings'];report={'status':'CONTACT_BASE_REQUIRES_AUDIT','body_mesh_coordinates_changed':False,'new_physics_solve':False}
disabled=[]
for mod in cloth.modifiers:
    if mod.name in ('Keep clothing outside posed skin','Sleeve clearance around moving forearms','Minimum gap at sleeve contact'):mod.show_viewport=False;mod.show_render=False;disabled.append(mod.name)
report['disabled_broad_contact_projections']=disabled
for mod in list(lining.modifiers):
    if mod.type=='SOLIDIFY':lining.modifiers.remove(mod)
report['lining']='single fabric surface outside complete skin; no inward solidify walls'
mesh=body.data;mask=mesh.attributes.get('OutfitContactNylonLiveFaces') or mesh.attributes.new('OutfitContactNylonLiveFaces','BOOLEAN','FACE');old=mesh.attributes['OutfitNylonFaces'];foot=mesh.attributes['OutfitNylonFoot']
for face,value in zip(mesh.polygons,mask.data):value.value=old.data[face.index].value or all(foot.data[i].value for i in face.vertices)
tree=stock.modifiers['Nylon from evaluated body surface'].node_group;n=tree.nodes;l=tree.links;field=next(node for node in n if node.bl_idname=='GeometryNodeInputNamedAttribute' and node.inputs['Name'].default_value=='OutfitNylonFaces' and node.outputs['Attribute'].is_linked and any(link.to_node.bl_idname=='GeometryNodeSeparateGeometry' and link.to_node.inputs['Geometry'].is_linked and link.to_node.inputs['Geometry'].links[0].from_node.bl_idname=='GeometryNodeSetPosition' for link in node.outputs['Attribute'].links));field.inputs['Name'].default_value='OutfitContactNylonLiveFaces';select=next(link.to_node for link in field.outputs['Attribute'].links);setmat=next(node for node in n if node.bl_idname=='GeometryNodeSetMaterial');l.new(select.outputs['Selection'],setmat.inputs['Geometry']);join=next(node for node in n if node.bl_idname=='GeometryNodeJoinGeometry')
for link in list(join.inputs['Geometry'].links):l.remove(link)
l.new(setmat.outputs['Geometry'],join.inputs['Geometry']);report['nylon']='complete live body and foot surface with continuous topology; old foot fabric overlay removed, body and shoes preserved'
mesh.update();body.update_tag(refresh={'DATA'});bpy.context.scene.frame_set(325);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_ContactBase.blend'),compress=True);(out/'base_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('OUTFIT_CONTACT_BASE',json.dumps(report),flush=True)
