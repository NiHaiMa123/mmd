import sys,json,argparse
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords,crosses
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--out',required=True);p.add_argument('--mark-render',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out);out.mkdir(exist_ok=True,parents=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.delivery)/'完整角色_整头连续物理_15秒.blend'),load_ui=False,use_scripts=False);m=bpy.data.objects['东雪莲x达妮娅_素体'];s=bpy.context.scene;m.data.calc_loop_triangles();tri=np.array([t.vertices[:] for t in m.data.loop_triangles]);mi=np.array([m.data.polygons[t.polygon_index].material_index for t in m.data.loop_triangles]);attr=m.data.attributes['SurfaceClass'];cls=np.array([attr.data[t.polygon_index].value for t in m.data.loop_triangles]);shadow=np.flatnonzero([m.material_slots[i].material.name=='HairShadow' for i in mi]);skin=np.flatnonzero(np.isin(cls,[1,2]));rows=[]
for f in [326,331,336]:
 s.frame_set(f);bpy.context.view_layer.update();co=coords(m);v=[Vector(x) for x in co];aa=BVHTree.FromPolygons(co.tolist(),tri[shadow].tolist(),all_triangles=True);bb=BVHTree.FromPolygons(co.tolist(),tri[skin].tolist(),all_triangles=True);hits=[(int(shadow[i]),int(skin[j])) for i,j in aa.overlap(bb) if crosses([v[k] for k in tri[shadow[i]]],[v[k] for k in tri[skin[j]]])];rows.append(dict(frame=f,shadow_skin_crossings=len(hits),witnesses=hits[:20],shadow_bbox=[co[np.unique(tri[shadow])].min(0).tolist(),co[np.unique(tri[shadow])].max(0).tolist()]));print('HAIR_SHADOW_CROSSINGS',f,len(hits),flush=True)
materials={}
for name in ['Hair','HairShadow','Body']:
 mat=bpy.data.materials[name];nodes=[]
 for n in mat.node_tree.nodes:
  inputs={i.name:str(i.default_value) for i in n.inputs if hasattr(i,'default_value') and not i.is_linked};nodes.append(dict(name=n.name,type=n.bl_idname,inputs=inputs))
 materials[name]=dict(nodes=nodes,links=[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links])
(out/'shadow_inspection.json').write_text(json.dumps(dict(rows=rows,materials=materials),ensure_ascii=False,indent=2),encoding='utf8')
if a.mark_render:
 mat=bpy.data.materials['HairShadow'];mat.node_tree.nodes.clear();emit=mat.node_tree.nodes.new('ShaderNodeEmission');emit.inputs['Color'].default_value=(1,.1,0,1);output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');mat.node_tree.links.new(emit.outputs[0],output.inputs['Surface']);prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
 for d in prefs.devices:d.use=d.type=='OPTIX'
 s.cycles.device='GPU';s.cycles.samples=8;s.frame_set(326);s.render.filepath=str(out/'shadow_id_326.png');bpy.ops.render.render(write_still=True)
