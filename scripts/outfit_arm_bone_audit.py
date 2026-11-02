"""Compare original arm rest layouts and exported arm rigid-body filters."""
from pathlib import Path
import sys,argparse
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve()
profile=read_json(job/'profile_snapshot.json');result=read_json(job/'result.json');ie=engine('import_export')
report={}
for label,path in [('source',profile['source']['path']),('target',profile['target']['path']),('fitted',result['pmx'])]:
    ie.clear_scene();obs=ie.import_pmx(path);arm=next(o for o in obs if o.type=='ARMATURE')
    bones={b.name:{'head':list(b.head_local),'tail':list(b.tail_local),'parent':b.parent.name if b.parent else None}
           for b in arm.data.bones if b.name.startswith(('腕','ひじ','手捩','手首','袖_'))}
    rigids=[r for r in obs if getattr(r,'mmd_type','')=='RIGID_BODY']
    arm_rigids=[r for r in rigids if r.mmd_rigid.bone.startswith(('腕','ひじ','袖_','手首'))]
    rows=[{'name':r.name,'bone':r.mmd_rigid.bone,'mode':r.mmd_rigid.type,
           'group':r.mmd_rigid.collision_group_number,'exclude_groups':[i for i,v in enumerate(r.mmd_rigid.collision_group_mask) if v],
           'position':list(r.location),'size':list(r.mmd_rigid.size)} for r in arm_rigids]
    report[label]={'bones':bones,'rigids':rows}
write_json(out,report)
print('ARM_BONES_READY',str(out),flush=True)
