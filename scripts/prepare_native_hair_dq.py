"""Use Blender's standard Preserve Volume skinning on a complete hair copy."""
import argparse,bpy,bmesh,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True)
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=a.source,use_scripts=False,load_ui=False)
s=bpy.context.scene;s.frame_set(1);m=bpy.data.objects['东雪莲x达妮娅_素体']
ids=np.load(ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware/hair_ids.npy')
attr=m.data.attributes.get('SourceVertexID') or m.data.attributes.new('SourceVertexID','INT','POINT');attr.data.foreach_set('value',np.arange(len(m.data.vertices),dtype=np.int32))
hair=m.copy();hair.data=m.data.copy();hair.name='完整头发_原生DQ蒙皮_全部发片';s.collection.objects.link(hair)
for md in list(hair.modifiers):
 if md.type!='ARMATURE':hair.modifiers.remove(md)
hair.hide_set(False);hair.hide_viewport=False;hair.hide_render=False
bpy.ops.object.select_all(action='DESELECT');hair.select_set(True);bpy.context.view_layer.objects.active=hair;s.tool_settings.mesh_select_mode=(True,False,False)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.reveal(select=False);bpy.ops.mesh.select_all(action='DESELECT');bm=bmesh.from_edit_mesh(hair.data);layer=bm.verts.layers.int['SourceVertexID'];keep=set(map(int,ids))
for v in bm.verts:v.select_set(int(v[layer]) not in keep)
bmesh.update_edit_mesh(hair.data);bpy.ops.mesh.delete(type='VERT');bpy.ops.object.mode_set(mode='OBJECT')
assert set(v.value for v in hair.data.attributes['SourceVertexID'].data)==keep
next(md for md in hair.modifiers if md.type=='ARMATURE').use_deform_preserve_volume=True
mask=m.vertex_groups.new(name='DQ_独立显示全部头发');mask.add(ids.tolist(),1.,'REPLACE');md=m.modifiers.new('全部头发由原生DQ副本显示','MASK');md.vertex_group=mask.name;md.invert_vertex_group=True
s['HairDisplayObject']=hair.name
for obj in bpy.data.objects:
 for md in obj.modifiers:
  if md.type=='MESH_CACHE':md.filepath=bpy.path.abspath(md.filepath)
path=out/'完整角色_JigglePhysics_DQ_15秒.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
(out/'configuration.json').write_text(json.dumps(dict(source=a.source,method='Unmodified upstream Jiggle bake plus stock Blender Armature Preserve Volume',hair_vertices=len(ids),hair_triangles=len(hair.data.polygons),original_weights_modified=False,reference='https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/armature.html'),ensure_ascii=False,indent=2),'utf8')
print('DQ_SETUP_READY',str(path),flush=True)
