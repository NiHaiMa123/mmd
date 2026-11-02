"""Identify actual surfaces at small discolored corset triangles."""
import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/chest_hd/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);cloth=bpy.data.objects['Cloth'];attribute=cloth.data.attributes.new('ChestAuditOriginalFace','INT','FACE');attribute.data.foreach_set('value',list(range(len(cloth.data.polygons))));islands=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'];face_island={fi:k for k,c in enumerate(islands) for fi in c['faces']};bpy.context.scene.frame_set(496);arm=bpy.data.objects['达妮娅_arm'];target=arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.055,.015));dg=bpy.context.evaluated_depsgraph_get();meshes={}
for name in ('Cloth','Stockings','达妮娅_mesh'):
 obj=bpy.data.objects[name];ev=obj.evaluated_get(dg);mesh=ev.to_mesh();mesh.calc_loop_triangles();points=[obj.matrix_world@v.co for v in mesh.vertices];triangles=list(mesh.loop_triangles);tree=BVHTree.FromPolygons(points,[tuple(t.vertices) for t in triangles],all_triangles=True);meshes[name]=(mesh,points,triangles,tree)
report=[]
for x,y in ((645,750),(705,758),(799,754),(700,720),(580,748)):
 origin=target+Vector(((x/1080-.5)*.34,-2,(.5-y/1080)*.34));hits=[]
 for name,(mesh,points,triangles,tree) in meshes.items():
  hit,normal,ti,d=tree.ray_cast(origin,Vector((0,1,0)),4)
  if hit is None:continue
  tri=triangles[ti];mat=mesh.materials[tri.material_index];uv=barycentric_transform(hit,*(points[j] for j in tri.vertices),*(Vector((*mesh.uv_layers.active.data[li].uv,0)) for li in tri.loops));textures=[]
  for node in mat.node_tree.nodes if mat.node_tree else []:
   if node.type!='TEX_IMAGE' or not node.image or not node.image.has_data:continue
   image=node.image;w,h=image.size;ix=min(w-1,max(0,int((uv.x%1)*w)));iy=min(h-1,max(0,int((uv.y%1)*h)));pixel=(iy*w+ix)*image.channels;rgba=list(image.pixels[pixel:pixel+image.channels]);textures.append({'image':image.name,'rgba':rgba})
  original_face=mesh.attributes['ChestAuditOriginalFace'].data[tri.polygon_index].value if mesh.attributes.get('ChestAuditOriginalFace') else None
  hits.append({'object':name,'distance':d,'material':mat.mmd_material.name_j,'position':list(hit),'polygon':tri.polygon_index,'original_face':original_face,'original_island':face_island.get(original_face) if name=='Cloth' else None,'uv':list(uv),'textures':textures})
 report.append({'pixel':[x,y],'hits':sorted(hits,key=lambda value:value['distance'])})
(ROOT/'outputs/cynical_cloth15/chest_hd/corset_pixel_trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('CORSET_PIXEL_TRACE',json.dumps(report,ensure_ascii=False),flush=True)
