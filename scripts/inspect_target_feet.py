import argparse,sys
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
profile,result=[read_json(job/n) for n in ('profile_snapshot.json','result.json')]
ie=engine('import_export');ie.clear_scene();objects=ie.import_pmx(profile['target']['path']);mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE')
names={g.index:g.name for g in mesh.vertex_groups};report={'bones':{},'feet':{}}
for b in arm.data.bones:
    if b.name.endswith(('.L','.R')) and b.name.startswith(('足首','足先','つま先','足ＩＫ','つま先ＩＫ')):
        report['bones'][b.name]={'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None}
for side,sign in [('L',1),('R',-1)]:
    ankle=arm.data.bones['足首.'+side].head_local
    ids={i for f in mesh.data.polygons if mesh.data.materials[f.material_index].name in ('Body','Nails') for i in f.vertices
         if mesh.data.vertices[i].co.x*sign>0 and mesh.data.vertices[i].co.z<ankle.z+.05}
    report['feet'][side]={'vertices':len(ids),'min':[min(mesh.data.vertices[i].co[j] for i in ids) for j in range(3)],'max':[max(mesh.data.vertices[i].co[j] for i in ids) for j in range(3)],
        'points':[{'id':i,'p':list(mesh.data.vertices[i].co),'weights':{names[e.group]:e.weight for e in mesh.data.vertices[i].groups if e.weight>1e-6 and not names[e.group].startswith('mmd_')}} for i in sorted(ids)]}
write_json(out/'target_feet.json',report)
print('TARGET_FOOT_BONES',report['bones'],flush=True)
