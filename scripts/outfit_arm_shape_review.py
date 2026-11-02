"""Verify source sleeve coordinates survived the anatomical rigid mapping."""
import argparse,sys
from pathlib import Path
import bpy
from mathutils import Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);job=Path(a.job).resolve();out=Path(a.out).resolve()
result,profile=[read_json(job/n) for n in ('result.json','profile_snapshot.json')]
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=result['blend'])
cloth=next(o for o in ie.model_meshes() if o.get('mmd_garment'))
tree=KDTree(len(cloth.data.vertices))
for v in cloth.data.vertices:tree.insert(v.co,v.index)
tree.balance()
objects=ie.import_pmx(profile['source']['path']);source=ie.model_meshes(objects)[0]
names={g.index:g.name for g in source.vertex_groups};materials=set(profile['selected_materials'])
used={i for f in source.data.polygons
      if source.data.materials[f.material_index].mmd_material.name_j in materials
      or source.data.materials[f.material_index].name in materials for i in f.vertices}
reports=[]
for row in result['adaptations']['arm_rest']['sides']:
    allowed=set(row['bones']);delta=Matrix(row['matrix']);samples=[]
    for i in sorted(used):
        weights=[(names[g.group],g.weight) for g in source.data.vertices[i].groups if g.weight>1e-7 and not names[g.group].startswith('mmd_')]
        if not weights or not all(n in allowed for n,w in weights):continue
        expected=delta@source.data.vertices[i].co
        _,matched,distance=tree.find(expected)
        samples.append({'source_vertex':i,'fitted_vertex':matched,'error_m':distance})
    reports.append({'side':row['side'],'samples':len(samples),'max_error_m':max((v['error_m'] for v in samples),default=0),
                    'unmatched_vertices':[v for v in samples if v['error_m']>1e-5]})
passed=all(r['samples']>0 and not r['unmatched_vertices'] for r in reports)
report={'passed':passed,'sides':reports,'tolerance_m':1e-5,
        'scope':'source garment vertices whose positive weights all share the anatomical arm delta; coordinate-set correspondence, not visibility or dynamics acceptance'}
write_json(out,report);print('ARM_SHAPE_REVIEW',report,flush=True)
if not passed:raise SystemExit(1)
