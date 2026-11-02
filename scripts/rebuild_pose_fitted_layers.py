"""Rebuild tight fabric on the validated exterior while retaining source assets.

This is a single-pose reconstruction experiment, not a cloth simulation or a
dynamic garment binding. Texture coordinates are sampled from the rest outfit.
"""
import argparse,sys,json
from pathlib import Path
from collections import Counter
import bpy,numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.motion_contact import SKIN
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(Path(a.input).resolve()),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(325);cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];proxy=bpy.data.objects['Outfit_ClosedSkinContactProxy'];cloth.data.calc_loop_triangles();rest=np.array([v.co[:] for v in cloth.data.vertices]);faces=np.array([t.vertices[:] for t in cloth.data.loop_triangles]);_,weld=np.unique(np.rint(rest/1e-6).astype(np.int64),axis=0,return_inverse=True);parent=np.arange(weld.max()+1)
def root(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in weld[faces]:
    for i in f[1:]:parent[root(int(i))]=root(int(f[0]))
labels=np.array([root(int(i)) for i in weld]);core=np.isin(labels,[13948,5977]);tris=[t for t in cloth.data.loop_triangles if np.all(core[list(t.vertices)])];rest_tree=BVHTree.FromPolygons(rest.tolist(),[t.vertices[:] for t in tris],all_triangles=True);rest_normals=[]
for t in tris:
    v=rest[list(t.vertices)];n=np.cross(v[1]-v[0],v[2]-v[0]);rest_normals.append(n/max(np.linalg.norm(n),1e-12))
rest_normals=np.array(rest_normals);uv=cloth.data.uv_layers.active
def capture(obj,skin_only=False):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();co=np.array([v.co[:] for v in mesh.vertices]);faces=np.array([t.vertices[:] for t in mesh.loop_triangles if not skin_only or mesh.materials[t.material_index].name in SKIN|{'Nails'}]);ev.to_mesh_clear();m=np.array(obj.matrix_world);return co@m[:3,:3].T+m[:3,3],faces
skin,sf=capture(body,True);skin_tree=BVHTree.FromPolygons(skin.tolist(),sf.tolist(),all_triangles=True);points,pf=capture(proxy);proxy.data.update();normal=np.array([v.normal[:] for v in proxy.data.vertices]);brest=np.array([v.co[:] for v in body.data.vertices]);brnames={g.index:g.name for g in body.vertex_groups if g.name in arm.data.bones};dominant=[max(((g.weight,brnames[g.group]) for g in v.groups if g.group in brnames),default=(0.,''))[1] for v in body.data.vertices];to_cloth=np.linalg.inv(np.array(cloth.matrix_world))@np.array(body.matrix_world);brest=brest@to_cloth[:3,:3].T+to_cloth[:3,3];selected=[];face_uv=[];face_mat=[];lining_faces=[];counts=Counter();cache={}
def rest_sample(point):
    q,n,j,d=skin_tree.find_nearest(Vector(point));ids=sf[j];v=skin[ids];w=barycentric_transform(q,*(Vector(p) for p in v),Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)));w=np.array(w);rp=w@brest[ids];rn=np.cross(brest[ids[1]]-brest[ids[0]],brest[ids[2]]-brest[ids[0]]);rn/=max(np.linalg.norm(rn),1e-12);return rp,rn,Counter(dominant[i] for i in ids).most_common(1)[0][0]
def garment_sample(point,normal):
    origin=point-normal*.16;distance=0.;last=None
    for _ in range(20):
        q,n,j,d=rest_tree.ray_cast(Vector(origin),Vector(normal),.34-distance)
        if q is None:break
        distance=float(np.linalg.norm(np.array(q)-(point-normal*.16)));origin=np.array(q)+normal*.00002
        if n.dot(Vector(normal))>.05:last=(q,j)
        if distance>.339:break
    return last
for k,f in enumerate(pf):
    rp,rn,bone=rest_sample(points[f].mean(axis=0));is_core=bone.startswith(('上半身','下半身','胸','乳','腰','腹','おっぱい','首')) and .86<rp[2]<1.37
    if is_core:
        sample=garment_sample(rp,rn)
        if sample:
            q,j=sample;selected.append(k);face_mat.append(tris[j].material_index);face_uv.append(j);counts['core_faces']+=1
    if bone.startswith(('腕','肩')) and 1.08<rp[2]<1.30:lining_faces.append(k);counts['lining_faces']+=1
    if k%150000==0:print('REBUILD_FITTED_LAYERS',k,json.dumps(counts),flush=True)
def exterior_mesh(name,chosen,offset):
    used=np.unique(pf[chosen]);lookup=np.full(len(points),-1,dtype=int);lookup[used]=np.arange(len(used));co=points[used]+normal[used]*offset;inverse=np.linalg.inv(np.array(cloth.matrix_world));co=co@inverse[:3,:3].T+inverse[:3,3];mesh=bpy.data.meshes.new(name);mesh.from_pydata(co.tolist(),[],lookup[pf[chosen]].tolist());mesh.update()
    for polygon in mesh.polygons:polygon.use_smooth=True
    obj=bpy.data.objects.new(name,mesh);scene.collection.objects.link(obj);obj.matrix_world=cloth.matrix_world.copy();obj.hide_render=True;obj.hide_set(True);obj['outfit_backup']=True;return obj,used
coat,used=exterior_mesh('ExteriorFittedTorso',selected,.0015)
for material in cloth.data.materials:coat.data.materials.append(material)
new_uv=coat.data.uv_layers.new(name=uv.name)
for polygon,source_index,material in zip(coat.data.polygons,face_uv,face_mat):
    polygon.material_index=int(material);tri=tris[source_index];v=[Vector(rest[i]) for i in tri.vertices];tuv=[Vector((*uv.data[i].uv,0.)) for i in tri.loops]
    for li in polygon.loop_indices:
        old=used[coat.data.loops[li].vertex_index]
        if int(old) not in cache:cache[int(old)]=rest_sample(points[old])[:2]
        # All corners must use the face's material and source UV triangle.
        # A new ray per corner may select another overlaid material/atlas.
        rp,rn=cache[int(old)];tri_normal=rest_normals[source_index];denom=float(np.dot(rn,tri_normal));q=rp.copy()
        if abs(denom)>.05:q=rp+rn*(np.dot(rest[tri.vertices[0]]-rp,tri_normal)/denom)
        uv_point=barycentric_transform(Vector(q),*v,*tuv)
        new_uv.data[li].uv=uv_point.xy
mask=cloth.data.attributes.get('OutfitReplaceTightTorso') or cloth.data.attributes.new('OutfitReplaceTightTorso','BOOLEAN','FACE')
for face,flag in zip(cloth.data.polygons,mask.data):flag.value=bool(np.all(core[list(face.vertices)]))
def replacement_group(obj,helper,partial=False):
    nt=bpy.data.node_groups.new(obj.name+'_ExteriorFabric325','GeometryNodeTree');nt.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry');nt.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry');n,l=nt.nodes,nt.links;inp=n.new('NodeGroupInput');info=n.new('GeometryNodeObjectInfo');info.transform_space='RELATIVE';info.inputs['Object'].default_value=helper;output=n.new('NodeGroupOutput')
    if partial:
        field=n.new('GeometryNodeInputNamedAttribute');field.data_type='BOOLEAN';field.inputs['Name'].default_value='OutfitReplaceTightTorso';delete=n.new('GeometryNodeDeleteGeometry');delete.domain='FACE';l.new(inp.outputs['Geometry'],delete.inputs['Geometry']);l.new(field.outputs['Attribute'],delete.inputs['Selection']);join=n.new('GeometryNodeJoinGeometry');l.new(delete.outputs['Geometry'],join.inputs['Geometry']);l.new(info.outputs['Geometry'],join.inputs['Geometry']);l.new(join.outputs['Geometry'],output.inputs['Geometry'])
    else:l.new(info.outputs['Geometry'],output.inputs['Geometry'])
    obj.modifiers.new('Exterior fitted fabric pose 325','NODES').node_group=nt
replacement_group(cloth,coat,True);lining,used=exterior_mesh('ExteriorFittedSleeveLining',lining_faces,.0008);lining.data.materials.append(bpy.data.objects['SleeveLining'].data.materials[0] if len(bpy.data.objects['SleeveLining'].data.materials) else bpy.data.materials['Keqing_FittedSleeveLining']);replacement_group(bpy.data.objects['SleeveLining'],lining);report={'status':'REBUILT_STATIC_FABRIC_REQUIRES_AUDIT','frame':325,'body_changed':False,'physics':False,'replacement_torso_faces':len(selected),'replacement_lining_faces':len(lining_faces),'source_mesh_and_uv_preserved':True};scene.frame_start=325;scene.frame_end=325;bpy.ops.wm.save_as_mainfile(filepath=str(out/'Outfit_RebuiltLayers325.blend'),compress=True);(out/'rebuild_report.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
