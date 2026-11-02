"""Measure whether crossing cuff faces can be influenced by PMX physics at all."""
from pathlib import Path
import argparse,sys
from collections import Counter
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--faces',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve();ids=read_json(Path(a.faces).resolve())
ie=engine('import_export');ie.clear_scene();objects=ie.import_pmx(read_json(job/'result.json')['pmx']);mesh=ie.model_meshes(objects)[0]
rigids=[o for o in objects if getattr(o,'mmd_type','')=='RIGID_BODY']
dynamic={r.mmd_rigid.bone for r in rigids if str(r.mmd_rigid.type) in ('1','2')}
groups={g.index:g.name for g in mesh.vertex_groups};rows=[]
for fi in ids:
    face=mesh.data.polygons[fi];mat=mesh.data.materials[face.material_index].name
    fractions=[sum(e.weight for e in mesh.data.vertices[i].groups if groups[e.group] in dynamic) for i in face.vertices]
    rows.append({'face':fi,'material':mat,'dynamic_weight_per_vertex':fractions})
zero=[r for r in rows if max(r['dynamic_weight_per_vertex'])<1e-6]
arm=[r for r in rigids if r.mmd_rigid.bone.startswith(('腕.','ひじ.','手首.'))]
sleeve=[r for r in rigids if r.mmd_rigid.bone.startswith('袖_')]
pairs=[{'arm':ar.mmd_rigid.bone,'sleeve':sr.mmd_rigid.bone,
        'allowed':not(ar.mmd_rigid.collision_group_mask[sr.mmd_rigid.collision_group_number]
                       or sr.mmd_rigid.collision_group_mask[ar.mmd_rigid.collision_group_number])}
       for ar in arm for sr in sleeve if ar.mmd_rigid.bone[-2:]==sr.mmd_rigid.bone[-2:]]
report={'crossing_faces':len(rows),'zero_dynamic_weight_faces':len(zero),
        'zero_by_material':dict(Counter(r['material'] for r in zero)),
        'arm_sleeve_collision_pairs':pairs,'faces':rows,
        'scope':'selected forearm crossing faces from a no-physics preview; positive physics weights are necessary, not sufficient, for collision response'}
write_json(out,report);print('SLEEVE_PHYSICS_COVERAGE',{k:v for k,v in report.items() if k not in ('faces','arm_sleeve_collision_pairs')},flush=True)
