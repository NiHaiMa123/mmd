"""Recover every torso layer from its own original material/UV island."""
import sys,json
from pathlib import Path
from collections import defaultdict,Counter
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/structured_v2/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
cloth=bpy.data.objects['Cloth'];islands=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'];selected=[(k,c) for k,c in enumerate(islands) if c['bounds'][0][0]>-.151 and c['bounds'][1][0]<.151 and c['bounds'][0][2]>1.08 and c['bounds'][1][2]>1.145]
path=json.loads((ROOT/'outputs/keqing_head/proportions_v2/head_swap_report.json').read_text(encoding='utf-8'))['source'];source=ie.model_meshes(ie.import_pmx(path))[0];source.data.calc_loop_triangles();su=source.data.uv_layers.active;tu=cloth.data.uv_layers.active
affine=np.array(json.loads((ROOT/'outputs/chest_repair/source/source_coordinates.json').read_text(encoding='utf-8'))['affine'])
parent={};lookup=defaultdict(set)
normal_lookup=defaultdict(list)
def find(key):
 parent.setdefault(key,key)
 while parent[key]!=key:parent[key]=parent[parent[key]];key=parent[key]
 return key
for f in source.data.polygons:
 name=source.data.materials[f.material_index].mmd_material.name_j
 for i in f.vertices[1:]:parent[find((name,i))]=find((name,f.vertices[0]))
 for li in f.loop_indices:
  vertex=source.data.loops[li].vertex_index;lookup[(name,*[round(float(v),7) for v in su.data[li].uv])].add(vertex);normal_lookup[vertex].append(source.data.corner_normals[li].vector.copy())
vertex_normals={i:sum(values,Vector()).normalized() for i,values in normal_lookup.items()}
by_component=defaultdict(list)
for t in source.data.loop_triangles:
 name=source.data.materials[t.material_index].mmd_material.name_j;by_component[find((name,t.vertices[0]))].append(t)
cache={};recovered={};normals={};reports=[];allfaces=[]
all_triangles=defaultdict(list)
for t in source.data.loop_triangles:all_triangles[source.data.materials[t.material_index].mmd_material.name_j].append(t)
for island,c in selected:
 votes=Counter();name=next(iter(c['materials']));ids={i for fi in c['faces'] for i in cloth.data.polygons[fi].vertices}
 for fi in c['faces']:
  for li in cloth.data.polygons[fi].loop_indices:
   i=cloth.data.loops[li].vertex_index;key=(name,*[round(float(v),7) for v in tu.data[li].uv]);candidates=lookup.get(key,[])
   if candidates:
    j=min(candidates,key=lambda j:np.linalg.norm(np.append(source.data.vertices[j].co[:],1)@affine-np.array(cloth.data.vertices[i].co[:])))
    votes[find((name,j))]+=1
 if not votes:raise RuntimeError(f'No exact UV seed for torso island {island}')
 chosen=votes.most_common(1)[0][0]
 components=tuple(sorted(votes))
 if components not in cache:
  tris=[t for component in components for t in by_component[component]];uvpoints=[Vector((*su.data[li].uv,0)) for t in tris for li in t.loops];cache[components]=(BVHTree.FromPolygons(uvpoints,[(k*3,k*3+1,k*3+2) for k in range(len(tris))],all_triangles=True),tris)
 tree,tris=cache[components];errors=[]
 for fi in c['faces']:
  for li in cloth.data.polygons[fi].loop_indices:
   i=cloth.data.loops[li].vertex_index
   if str(i) in recovered:continue
   key=(name,*[round(float(v),7) for v in tu.data[li].uv]);exact=lookup.get(key,[])
   if exact:
    j=min(exact,key=lambda j:np.linalg.norm(np.append(source.data.vertices[j].co[:],1)@affine-np.array(cloth.data.vertices[i].co[:])))
    recovered[str(i)]=list(source.data.vertices[j].co);normals[str(i)]=list(vertex_normals[j]);errors.append(0.);continue
   hit,_,ti,d=tree.find_nearest(Vector((*tu.data[li].uv,0)))
   if hit is None or d>1e-4:
    # A subdivided fragment can contain no original source corner. Search
    # containing UV triangles, then disambiguate repeated atlas regions in 3D.
    point=Vector((*tu.data[li].uv,0));candidates=[]
    for t in all_triangles[name]:
     uvtri=[Vector((*su.data[j].uv,0)) for j in t.loops]
     if any(point[axis]<min(v[axis] for v in uvtri)-1e-6 or point[axis]>max(v[axis] for v in uvtri)+1e-6 for axis in (0,1)):continue
     if (uvtri[1]-uvtri[0]).cross(uvtri[2]-uvtri[0]).length<1e-12:continue
     w=barycentric_transform(point,*uvtri,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
     if min(w)<-1e-4:continue
     co=barycentric_transform(point,*uvtri,*(source.data.vertices[j].co for j in t.vertices));distance=np.linalg.norm(np.append(co[:],1)@affine-np.array(cloth.data.vertices[i].co[:]))
     normal=barycentric_transform(point,*uvtri,*(source.data.corner_normals[j].vector for j in t.loops)).normalized();candidates.append((distance,co,normal))
    if not candidates:raise RuntimeError(f'No containing UV triangle island {island} vertex {i}')
    distance,co,normal=min(candidates,key=lambda item:item[0]);recovered[str(i)]=list(co);normals[str(i)]=list(normal);errors.append(0.);continue
   candidates=[]
   for close,_,triangle,distance_uv in tree.find_nearest_range(Vector((*tu.data[li].uv,0)),max(1e-6,d+1e-7)):
    t=tris[triangle];uvtri=[Vector((*su.data[j].uv,0)) for j in t.loops]
    if (uvtri[1]-uvtri[0]).cross(uvtri[2]-uvtri[0]).length<1e-12:continue
    co=barycentric_transform(close,*uvtri,*(source.data.vertices[j].co for j in t.vertices));normal=barycentric_transform(close,*uvtri,*(source.data.corner_normals[j].vector for j in t.loops)).normalized();spatial_error=np.linalg.norm(np.append(co[:],1)@affine-np.array(cloth.data.vertices[i].co[:]))
    candidates.append((spatial_error,co,normal,distance_uv))
   if not candidates:raise RuntimeError(f'Degenerate source UV triangle at {i}')
   _,co,normal,d=min(candidates,key=lambda value:value[0]);recovered[str(i)]=list(co);normals[str(i)]=list(normal);errors.append(d)
 reports.append({'island':island,'vertices':len(ids),'faces':len(c['faces']),'source_component':list(chosen),'max_uv_error':max(errors,default=0)})
 allfaces+=c['faces']
accepted=[];rejected=[];allfaces=[];accepted_ids=set()
group_names={g.index:g.name for g in cloth.vertex_groups};deform_bones=set(bpy.data.objects['达妮娅_arm'].data.bones.keys())
for r in reports:
 c=islands[r['island']];ids={i for fi in c['faces'] for i in cloth.data.polygons[fi].vertices};expected=np.column_stack([np.array([recovered[str(i)] for i in ids]),np.ones(len(ids))])@affine;old=np.array([cloth.data.vertices[i].co[:] for i in ids]);distance=np.linalg.norm(expected-old,axis=1);r['max_affine_correction_m']=float(distance.max())
 arm_fraction=[]
 for i in ids:
  weights=[(group_names[g.group],g.weight) for g in cloth.data.vertices[i].groups if group_names[g.group] in deform_bones];total=sum(w for _,w in weights);arm_fraction.append(sum(w for name,w in weights if any(part in name for part in ('腕','肩','ひじ','手')))/max(total,1e-8))
 r['original_arm_weight_mean']=float(np.mean(arm_fraction))
 # Torso bounds alone also catch metal triangles attached to the upper arms.
 # A source-space gate excludes these unrelated fragments from chest repair.
 if distance.max()>.065 or np.max(np.abs(expected[:,0]))>.16 or r['original_arm_weight_mean']>.3:
  rejected.append(r);continue
 accepted.append(r);allfaces+=c['faces'];accepted_ids.update(str(i) for i in ids)
report={'affine':affine.tolist(),'source':path,'vertices':{i:recovered[i] for i in accepted_ids},'normals':{i:normals[i] for i in accepted_ids},'faces':allfaces,'islands':accepted,'excluded_non_torso_or_ambiguous':rejected}
out=ROOT/'outputs/chest_repair/source/torso_coordinates.json';out.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8');print('TORSO_RECOVERED',len(accepted_ids),len(allfaces),len(accepted),'excluded',len(rejected),flush=True)
# Inventory actual torso skin, independent of broad arm-region counts.
body=bpy.data.objects['达妮娅_mesh'];mesh=body.data
for z in (1.10,1.18,1.24,1.30):
 points=[v.co[:] for v in mesh.vertices if abs(v.co.x)<.09 and abs(v.co.z-z)<.012]
 print('BODY_SLICE',z,len(points),np.min(points,axis=0).tolist() if points else None,np.max(points,axis=0).tolist() if points else None,flush=True)
