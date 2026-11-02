"""Recover original garment coordinates by preserved material and UV keys."""
import sys,json
from pathlib import Path
from collections import defaultdict
import bpy,numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/structured_v2/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);cloth=bpy.data.objects['Cloth'];faces=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'][2]['faces'];ids=sorted({i for fi in faces for i in cloth.data.polygons[fi].vertices});path=json.loads((ROOT/'outputs/keqing_head/proportions_v2/head_swap_report.json').read_text(encoding='utf-8'))['source'];objects=ie.import_pmx(path);source=ie.model_meshes(objects)[0];lookup=defaultdict(set);uv=source.data.uv_layers.active
for f in source.data.polygons:
    name=source.data.materials[f.material_index].mmd_material.name_j
    for li in f.loop_indices:lookup[(name,*[round(float(c),7) for c in uv.data[li].uv])].add(source.data.loops[li].vertex_index)
trees={}
for name in {key[0] for key in lookup}:
    points=[(Vector((*key[1:],0)),i) for key,values in lookup.items() if key[0]==name for i in values];tree=KDTree(len(points))
    for point,i in points:tree.insert(point,i)
    tree.balance();trees[name]=tree
uv=cloth.data.uv_layers.active;mapping={};ambiguous=0;fallback=[]
for f in cloth.data.polygons:
    name=cloth.data.materials[f.material_index].mmd_material.name_j
    for li in f.loop_indices:
        key=(name,*[round(float(c),7) for c in uv.data[li].uv]);candidates=lookup.get(key,[]);i=cloth.data.loops[li].vertex_index
        if not candidates and name in trees:
            near=trees[name].find_n(Vector((*uv.data[li].uv,0)),8);minimum=near[0][2]
            if minimum<.002:candidates=[j for _,j,d in near if d<minimum+1e-6];fallback.append(minimum)
        if candidates:
            j=min(candidates,key=lambda j:(source.data.vertices[j].co-cloth.data.vertices[i].co).length);mapping[i]=j;ambiguous+=len(candidates)>1
source.data.calc_loop_triangles();uvsource=source.data.uv_layers.active;by_material=defaultdict(list)
parent={v.index:v.index for v in source.data.vertices}
def find(i):
    while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
    return i
for f in source.data.polygons:
    if source.data.materials[f.material_index].mmd_material.name_j!='服':continue
    for i in f.vertices[1:]:parent[find(i)]=find(f.vertices[0])
seeds=defaultdict(int)
for i in ids:
    if i in mapping:seeds[find(mapping[i])]+=1
chosen=max(seeds,key=seeds.get);print('SOURCE_CHEST_COMPONENT',chosen,seeds[chosen],len(seeds),flush=True)
for tri in source.data.loop_triangles:
    name=source.data.materials[tri.material_index].mmd_material.name_j
    if name=='服' and find(tri.vertices[0])!=chosen:continue
    by_material[name].append(tri)
uv_trees={}
for name,triangles in by_material.items():
    positions=[Vector((*uvsource.data[li].uv,0)) for tri in triangles for li in tri.loops];tree=BVHTree.FromPolygons(positions,[(3*k,3*k+1,3*k+2) for k in range(len(triangles))],all_triangles=True);uv_trees[name]=(tree,triangles)
recovered={};recovered_normals={};uv_error=[]
for f in cloth.data.polygons:
    name=cloth.data.materials[f.material_index].mmd_material.name_j
    if name not in uv_trees:continue
    tree,triangles=uv_trees[name]
    for li in f.loop_indices:
        i=cloth.data.loops[li].vertex_index
        if i in recovered:continue
        point=Vector((*uv.data[li].uv,0));hit,_,ti,distance=tree.find_nearest(point)
        if hit is None or distance>.002:continue
        tri=triangles[ti];recovered[i]=barycentric_transform(hit,*(Vector((*uvsource.data[j].uv,0)) for j in tri.loops),*(source.data.vertices[j].co for j in tri.vertices));recovered_normals[i]=tri.normal.copy();uv_error.append(distance)
print('SOURCE_MAP_MATCHES',len(recovered),len(ids),sum(i in recovered for i in ids),'max_uv_distance',max(uv_error,default=0),flush=True)
assert all(i in recovered for i in ids),'Missing original chest UV correspondence'
x=np.array([recovered[i][:] for i in ids]);y=np.array([cloth.data.vertices[i].co[:] for i in ids]);design=np.column_stack([x,np.ones(len(x))]);affine=np.linalg.lstsq(design,y,rcond=None)[0];fit=design@affine;error=np.linalg.norm(fit-y,axis=1);out=ROOT/'outputs/chest_repair/source';out.mkdir(exist_ok=True);report={'mapped_vertices':len(recovered),'chest_vertices':len(ids),'mapping':'UV-triangle barycentric recovery supports subdivided vertices','max_uv_distance':max(uv_error,default=0),'affine':affine.tolist(),'rms_fit_m':float(np.sqrt((error**2).mean())),'max_fit_m':float(error.max()),'source':path,'vertices':{str(i):v[:] for i,v in recovered.items()},'normals':{str(i):recovered_normals[i][:] for i in ids}}
(out/'source_coordinates.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8');print('CHEST_SOURCE_MAP',json.dumps({k:v for k,v in report.items() if k!='vertices'},ensure_ascii=False),flush=True)
