"""Inspect material-local, seam-welded arm components without editing the model."""
from pathlib import Path
import argparse
import sys
from collections import Counter, defaultdict
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
ie=engine('import_export');ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=read_json(Path(a.job)/'result.json')['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'))
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
points=[cloth.matrix_world@v.co for v in cloth.data.vertices]
dom=engine('dressing').dominant_bones(cloth)
rows=[]
for mi,mat in enumerate(cloth.data.materials):
    faces=[f for f in cloth.data.polygons if f.material_index==mi]
    parent={i:i for f in faces for i in f.vertices};positions={}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(i,j):
        i,j=find(i),find(j)
        if i!=j:parent[j]=i
    for i in parent:
        key=tuple(round(c,6) for c in points[i])
        if key in positions:union(i,positions[key])
        else:positions[key]=i
    for f in faces:
        for i in f.vertices[1:]:union(f.vertices[0],i)
    comps=defaultdict(list);fs=defaultdict(list)
    for i in parent:comps[find(i)].append(i)
    for f in faces:fs[find(f.vertices[0])].append(f.index)
    for root,ids in comps.items():
        bones=Counter(dom[i] for i in ids)
        if len(ids)<12 or not any(n.startswith(('腕','ひじ')) and c>len(ids)*.1 for n,c in bones.items()):continue
        side=max(('L','R'),key=lambda s:sum(c for n,c in bones.items() if n.endswith('.'+s)))
        start=arm.matrix_world@arm.data.bones['腕.'+side].head_local
        end=arm.matrix_world@arm.data.bones['ひじ.'+side].head_local
        axis=(end-start).normalized();ts=[(points[i]-start).dot(axis) for i in ids]
        radii=[(points[i]-start-axis*(points[i]-start).dot(axis)).length for i in ids]
        rows.append(dict(material=mat.name,vertices=ids,faces=fs[root],count=len(ids),bones=dict(bones),side=side,
                         axial_bounds=[min(ts),max(ts)],upper_arm_length=(end-start).length,
                         radius_bounds=[min(radii),max(radii)],
                         radius_outliers=[{'id':ids[j],'co':list(points[ids[j]]),'bone':dom[ids[j]],'radius':radii[j]}
                                          for j in sorted(range(len(ids)),key=lambda j:radii[j],reverse=True)[:10]],
                         center=list(sum((points[i] for i in ids),Vector())/len(ids))))
write_json(Path(a.out),{'components':rows})
print('ARM_COMPONENTS',[(r['material'],r['side'],r['count'],r['bones'],r['axial_bounds']) for r in rows],flush=True)
