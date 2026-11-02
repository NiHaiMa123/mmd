"""Closed exterior skin proxy and continuous nylon shell for the checked pose.

The visible body is never replaced or trimmed. The proxy removes internal
anatomical surfaces from collision queries; stockings use its exterior only.
"""
import argparse,json,sys,subprocess
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN,triangle_crosses
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--method',choices=['filled','remesh'],default='filled');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh(preserve_all_data_layers=True,depsgraph=bpy.context.evaluated_depsgraph_get());mesh.calc_loop_triangles();world=np.array(body.matrix_world);co=np.array([v.co[:] for v in mesh.vertices]);co=co@world[:3,:3].T+world[:3,3];triangles=[t for t in mesh.loop_triangles if mesh.materials[t.material_index].name in SKIN|{'Nails'}];faces=np.array([t.vertices[:] for t in triangles]);source_loops=np.array([t.loops[:] for t in triangles]);source_rest=np.array([v.co[:] for v in body.data.vertices]);uvattr=mesh.attributes['OutfitNylonUV'];uv_values=np.array([v.vector[:] for v in uvattr.data]);design=np.array([v.value for v in mesh.attributes['tights_design_area'].data]);foot=np.array([v.value for v in mesh.attributes['OutfitNylonFoot'].data]);ev.to_mesh_clear();source_tree=BVHTree.FromPolygons(co.tolist(),faces.tolist(),all_triangles=True)
data=bpy.data.meshes.new('ClosedSkinContactProxy');data.from_pydata(co.tolist(),[],faces.tolist());data.update();bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);boundary=[e for e in bm.edges if e.is_boundary]
if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(data);bm.free();proxy=bpy.data.objects.new('Outfit_ClosedSkinContactProxy',data);scene.collection.objects.link(proxy);proxy.hide_render=True;proxy['outfit_backup']=True;proxy.select_set(True);bpy.context.view_layer.objects.active=proxy
if a.method=='filled':
    data.calc_loop_triangles();np.savez_compressed(out/'closed_source.npz',points=np.array([v.co[:] for v in data.vertices]),faces=np.array([t.vertices[:] for t in data.loop_triangles]));run=subprocess.run([str(ROOT/'tools/contact_stack/venv/Scripts/python.exe'),str(ROOT/'scripts/build_filled_voxel_shell.py'),'--input',str(out/'closed_source.npz'),'--output',str(out/'filled_shell.npz')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if run.returncode:raise RuntimeError(run.stderr.decode(errors='replace'))
    print(run.stdout.decode(errors='replace'),flush=True)
    with np.load(out/'filled_shell.npz') as z:points=z['points'].copy();quads=z['faces'].copy()
    replacement=bpy.data.meshes.new('FilledExteriorSkinProxy');replacement.from_pydata(points.tolist(),[],quads.tolist());replacement.update();proxy.data=replacement;smooth=proxy.modifiers.new('Exterior voxel smoothing','SMOOTH');smooth.factor=.5;smooth.iterations=3;bpy.ops.object.modifier_apply(modifier=smooth.name);expansion=.0003;voxel=.002
else:
    remesh=proxy.modifiers.new('Closed exterior voxel union','REMESH');remesh.mode='VOXEL';remesh.voxel_size=.0012;remesh.adaptivity=.15;remesh.use_smooth_shade=True;remesh.use_remove_disconnected=False;bpy.ops.object.modifier_apply(modifier=remesh.name);expansion=.0015;voxel=.0012
data=proxy.data;data.update();points=np.array([v.co[:] for v in data.vertices]);normals=np.array([v.normal[:] for v in data.vertices]);points+=normals*expansion;data.vertices.foreach_set('co',points.reshape(-1));data.update();data.calc_loop_triangles();pf=np.array([t.vertices[:] for t in data.loop_triangles]);report={'status':'BUILDING_STATIC_CLOSED_COLLIDER','frame':325,'body_coordinates_changed':False,'proxy_vertices':len(points),'proxy_triangles':len(pf),'voxel_m':voxel,'base_expansion_m':expansion,'method':a.method};print('CLOSED_SKIN_PROXY',json.dumps(report),flush=True)
# Enclose every source skin vertex with bounded, local outward corrections.
for iteration in range(8):
    target=BVHTree.FromPolygons(points.tolist(),pf.tolist(),all_triangles=True);sum_delta=np.zeros_like(points);count=np.zeros(len(points));outside=0
    for point in co[np.unique(faces)]:
        q,n,j,d=target.find_nearest(Vector(point))
        if (Vector(point)-q).dot(n)>.00001:
            outside+=1;ids=pf[j];sum_delta[ids]+=np.array(n)*(d+.0003);count[ids]+=1
    if not outside:break
    ids=count>0;points[ids]+=sum_delta[ids]/count[ids,None];print('ENCLOSE_VISIBLE_SKIN',iteration,outside,flush=True)
data.vertices.foreach_set('co',points.reshape(-1));data.update();data.calc_loop_triangles();pf=np.array([t.vertices[:] for t in data.loop_triangles]);target=BVHTree.FromPolygons(points.tolist(),pf.tolist(),all_triangles=True);crossings=0
for i,j in target.overlap(source_tree):
    if triangle_crosses([Vector(v) for v in points[pf[i]]],[Vector(v) for v in co[faces[j]]]):crossings+=1
report['original_skin_proxy_crossings']=crossings;report['last_outside_source_vertices']=outside;print('CLOSED_SKIN_CONTAINMENT',crossings,outside,flush=True)
# Select garment coverage using the source anatomical coordinates; the closed
# surface has no copied internal genital sheets and no individual toe pockets.
selected=[];nearest_cache={}
for i,f in enumerate(pf):
    point=points[f].mean(axis=0);q,n,j,d=source_tree.find_nearest(Vector(point));v=faces[j];t=co[v];uv=np.linalg.lstsq(np.column_stack((t[1]-t[0],t[2]-t[0])),np.array(q)-t[0],rcond=None)[0];bary=np.array([1-uv.sum(),uv[0],uv[1]]);rest=bary@source_rest[v]
    if (rest[2]<1.065 and abs(rest[0])<.205) or np.all(foot[v]):selected.append(i)
used=np.unique(pf[selected]);mapping=np.full(len(points),-1,dtype=int);mapping[used]=np.arange(len(used));nf=mapping[pf[selected]];nylon_points=points[used].copy();normals=np.array([v.normal[:] for v in data.vertices])[used];nylon_points+=normals*.00025;nylon_uv=np.empty((len(used),3));nylon_design=np.empty(len(used))
for k,i in enumerate(used):
    q,n,j,d=source_tree.find_nearest(Vector(points[i]));ids=faces[j];t=co[ids];uv=np.linalg.lstsq(np.column_stack((t[1]-t[0],t[2]-t[0])),np.array(q)-t[0],rcond=None)[0];bary=np.array([1-uv.sum(),uv[0],uv[1]]);nylon_uv[k]=bary@uv_values[source_loops[j]];nylon_design[k]=bary@design[ids]
inverse=np.linalg.inv(np.array(stock.matrix_world));nylon_points=nylon_points@inverse[:3,:3].T+inverse[:3,3];new=bpy.data.meshes.new('ContinuousExteriorNylon');new.from_pydata(nylon_points.tolist(),[],nf.tolist());new.materials.append(stock.data.materials[0]);new.update();attr=new.attributes.new('OutfitNylonUV','FLOAT_VECTOR','CORNER');attr.data.foreach_set('vector',nylon_uv[np.array([l.vertex_index for l in new.loops])].reshape(-1));field=new.attributes.new('tights_design_area','FLOAT','POINT');field.data.foreach_set('value',nylon_design);helper=bpy.data.objects.new('ContinuousExteriorNylon',new);scene.collection.objects.link(helper);helper.matrix_world=stock.matrix_world.copy();helper.hide_render=True;helper.hide_set(True);helper['outfit_backup']=True
tree=bpy.data.node_groups.new('Pose325_ContinuousNylon','GeometryNodeTree');tree.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');tree.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n,l=tree.nodes,tree.links;inp=n.new('NodeGroupInput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=helper;output=n.new('NodeGroupOutput');l.new(info.outputs['Geometry'],output.inputs['Geometry']);stock.modifiers.new('Continuous outer nylon pose 325','NODES').node_group=tree;proxy.hide_set(True);report.update(status='STATIC_CLOSED_SKIN_AND_NYLON_REQUIRES_AUDIT',nylon_vertices=len(nylon_points),nylon_triangles=len(nf),original_nylon_mesh_preserved=True);scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_ClosedSkin325.blend'),compress=True);(out/'closed_skin_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CONTINUOUS_NYLON_BUILT',json.dumps(report),flush=True)
