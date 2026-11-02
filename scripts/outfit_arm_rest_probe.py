"""Undo per-helper rest mapping and test an anatomical arm transform on copies."""
import argparse,sys
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
p.add_argument('--radial-scale',type=float,default=1.15)
p.add_argument('--rigid',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
result,request,profile=[read_json(job/n) for n in ('result.json','request.json','profile_snapshot.json')]
ie,dressing=engine('import_export'),engine('dressing');ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=result['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'));arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
source=ie.import_pmx(profile['source']['path']);target=ie.import_pmx(profile['target']['path'])
sa=next(o for o in source if o.type=='ARMATURE');ta=next(o for o in target if o.type=='ARMATURE')
used=set(g.name for g in cloth.vertex_groups)
mapping=dressing.build_rig_map(sa,ta,used)
old=dressing.rest_deltas(sa,ta,mapping['mapping']);old.update(dressing.garment_deltas(sa,mapping['garment_bones'],old))
lift=arm.data.bones['腕.L'].head_local-ta.data.bones['腕.L'].head_local
old={n:Matrix.Translation(lift)@m for n,m in old.items()}
new={n:m.copy() for n,m in old.items()};specs={};rows=[]
for side in ('L','R'):
    sh=sa.data.bones['腕.'+side].head_local;se=sa.data.bones['ひじ.'+side].head_local
    th=arm.data.bones['腕.'+side].head_local;te=arm.data.bones['ひじ.'+side].head_local
    axis=(se-sh).normalized();rotation=(se-sh).rotation_difference(te-th).to_matrix()
    scale=1. if a.rigid else (te-th).length/(se-sh).length
    radial=1. if a.rigid else a.radial_scale
    stretch=Matrix.Identity(3)*radial
    for i in range(3):
        for j in range(3):stretch[i][j]+=(scale-radial)*axis[i]*axis[j]
    delta=Matrix.Translation(th)@(rotation@stretch).to_4x4()@Matrix.Translation(-sh)
    for name in sa.data.bones.keys():
        if name.endswith('.'+side) and name.startswith(('腕','袖_')):
            new[name]=delta
            if name.startswith('袖_') or name in mapping['garment_bones']:
                b=sa.data.bones[name];specs[name]=(delta@b.head_local,delta@b.tail_local)
    rows.append({'side':side,'axial_scale':scale,'radial_scale':radial})
ids=set(i for c in read_json(ROOT/'outputs/outfit_v08_arm_inventory.json')['components'] for i in c['vertices'])
names={g.index:g.name for g in cloth.vertex_groups}
points=[v.co.copy() for v in cloth.data.vertices];original=[p.copy() for p in points]
for i in ids:
    weights=[(e.weight,names[e.group]) for e in cloth.data.vertices[i].groups if names[e.group] in old and e.weight>0]
    total=sum(w for w,n in weights)
    before=Matrix.Identity(4)*0;after=Matrix.Identity(4)*0
    for w,n in weights:before+=old[n]*(w/total);after+=new[n]*(w/total)
    points[i]=after@before.inverted()@points[i]
dressing.apply_positions(cloth.data,points)
# Update imported cloth chain rest coordinates and its rigid/joint transforms.
changes={n:new[n]@old[n].inverted() for n in specs if n in old}
rigids={o.name:o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY' and o not in source+target}
for r in rigids.values():
    delta=changes.get(r.mmd_rigid.bone)
    if delta is not None:
        r.matrix_world=delta@r.matrix_world
for obj in bpy.data.objects:
    if getattr(obj,'mmd_type','')=='JOINT' and obj not in source+target:
        rc=obj.rigid_body_constraint
        rs=[r for r in (rc.object1,rc.object2) if r is not None] if rc else []
        ns=[r.mmd_rigid.bone for r in rs]
        delta=next((changes[n] for n in ns if n in changes),None)
        if delta is not None:obj.matrix_world=delta@obj.matrix_world
bpy.context.view_layer.objects.active=arm;arm.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
try:
    for n,(head,tail) in specs.items():
        b=arm.data.edit_bones.get(n)
        if b is not None:b.head=head;b.tail=tail
finally:bpy.ops.object.mode_set(mode='OBJECT')
for obj in source+target:bpy.data.objects.remove(obj,do_unlink=True)
report={'method':'experimental_anatomical_arm_rest','parameters':rows,'vertices':len(ids),
        'max_displacement_m':max((points[i]-original[i]).length for i in ids),'experimental':True}
bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'));ie.export_pmx(str(out/'model.pmx'))
result.update(blend=str(out/'work.blend'),pmx=str(out/'model.pmx'),accepted=False,state='EXPERIMENTAL')
result.setdefault('adaptations',{})['arm_rest']=report
for n,value in [('result.json',result),('request.json',request),('profile_snapshot.json',profile),('arm_rest.json',report)]:write_json(out/n,value)
print('ARM_REST_PROBE',report,flush=True)
