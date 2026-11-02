import bpy,json
from pathlib import Path
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_plane_add(size=1,location=(0,0,1));surface=bpy.context.object
print('EMPTY_HAIR_OPERATOR',bpy.ops.object.curves_empty_hair_add.get_rna_type().description,flush=True)
bpy.ops.object.curves_empty_hair_add();hair=bpy.context.object
print('HAIR_OBJECT',hair.type,'SURFACE',hair.data.surface,'UV',hair.data.surface_uv_map,flush=True)
print('DATA_METHODS',[n for n in dir(hair.data) if not n.startswith('_')],flush=True)
print('HAIR_MODS',[(m.name,m.type,getattr(m,'node_group',None)) for m in hair.modifiers],flush=True)
print('SURFACE_MODS',[(m.name,m.type,getattr(m,'node_group',None)) for m in surface.modifiers],flush=True)
asset=Path('D:/software/blender/5.2.1/5.2/datafiles/assets/nodes/geometry_nodes_dynamics_assets.blend')
with bpy.data.libraries.load(str(asset),link=False) as (source,dest):dest.node_groups=list(source.node_groups)
for name in ('Hair Dynamics','Capture Rest Geometry','Get Attachment Surface','Setup Structural Rest Data','Sample Surface Deformation'):
 tree=bpy.data.node_groups.get(name)
 if tree:
  print('GROUP',name,[(s.name,s.in_out,s.socket_type,str(getattr(s,'default_value',''))) for s in tree.interface.items_tree if s.item_type=='SOCKET'],flush=True)
  if name in ('Hair Dynamics','Get Attachment Surface'):
   print('GROUP_NODES',name,[(n.name,n.bl_idname,getattr(n,'bundle_items',None)[:] if hasattr(n,'bundle_items') else None) for n in tree.nodes if n.bl_idname.startswith(('NodeMenu','GeometryNodeObjectInfo','GeometryNodeGroup','NodeGetBundleItem'))],flush=True)
print('CURVES_POINTS',[(p.identifier,p.type) for p in bpy.types.CurvePoint.bl_rna.properties] if hasattr(bpy.types,'CurvePoint') else '',flush=True)
