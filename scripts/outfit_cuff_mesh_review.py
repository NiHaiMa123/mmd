"""Compare exported cuff model against its baseline, including all morphs."""
import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine


def array(collection,prop,size,dtype=np.float32):
    values=np.empty(len(collection)*size,dtype=dtype)
    collection.foreach_get(prop,values)
    return values


def snapshot(job):
    ie=engine('import_export');ie.clear_scene()
    result=read_json(Path(job)/'result.json')
    objects=ie.import_pmx(result['pmx']);mesh=ie.model_meshes(objects)[0]
    names={g.index:g.name for g in mesh.vertex_groups}
    data=mesh.data
    return {
        'positions':array(data.vertices,'co',3),
        'loops':array(data.loops,'vertex_index',1,np.int32),
        'loop_materials':np.repeat(array(data.polygons,'material_index',1,np.int32),array(data.polygons,'loop_total',1,np.int32)),
        'materials':array(data.polygons,'material_index',1,np.int32),
        'material_names':[m.mmd_material.name_j for m in data.materials],
        'uv':{layer.name:array(layer.data,'uv',2) for layer in data.uv_layers},
        'morphs':{key.name:array(key.data,'co',3) for key in data.shape_keys.key_blocks},
        'weights':[{names[e.group]:e.weight for e in v.groups if e.weight>1e-7 and not names[e.group].startswith('mmd_')}
                   for v in data.vertices],
    }


def main():
    parser=argparse.ArgumentParser()
    for name in ('job','previous-job','out'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--allow-hand-domain-fix',action='store_true',help='Allow only the documented glove UV tie-resolution change')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    before,after=snapshot(args.previous_job),snapshot(args.job)
    def same(first,second):return first.shape==second.shape and np.array_equal(first,second)
    failures=[]
    unchanged={key:same(before[key],after[key]) for key in ('positions','loops','materials')}
    unchanged['material_names']=before['material_names']==after['material_names']
    for kind in ('uv','morphs'):
        unchanged[kind]=before[kind].keys()==after[kind].keys() and all(same(before[kind][n],after[kind][n]) for n in before[kind])
    uv_details={'before_layers':list(before['uv']),'after_layers':list(after['uv']),'layers':{}}
    for name in before['uv'].keys()&after['uv'].keys():
        a,b=before['uv'][name],after['uv'][name]
        if a.shape!=b.shape:continue
        delta=np.abs(a-b);indices=np.flatnonzero(delta>0)
        uv_details['layers'][name]={'max_abs_difference':float(delta.max(initial=0)),
            'changed_coordinates':len(indices),'samples':[
                {'loop':int(i//2),'axis':int(i%2),'before':float(a[i]),'after':float(b[i])}
                for i in indices[np.argsort(delta[indices])[-10:]]]}
    uv_exception=False
    if not unchanged['uv'] and args.allow_hand_domain_fix:
        uv_exception=before['uv'].keys()==after['uv'].keys()
        for name in before['uv'].keys()&after['uv'].keys():
            a,b=before['uv'][name],after['uv'][name]
            if a.shape!=b.shape:uv_exception=False;continue
            for loop in set(np.flatnonzero(a!=b)//2):
                vertex=int(after['loops'][loop]);material=after['material_names'][after['loop_materials'][loop]]
                allowed=('手首','親指','人指','中指','薬指','小指','手捩','ひじ','腕')
                if name!='UVMap' or material!='服' or not all(n.startswith(allowed) for n in after['weights'][vertex]):
                    uv_exception=False
    for key,value in unchanged.items():
        if not value and not (key=='uv' and uv_exception):failures.append('Changed '+key)
    if len(before['weights'])!=len(after['weights']):raise ValueError('Vertex order/count differs')
    changed=[];generated=[];unsupported=[]
    for index,(a,b) in enumerate(zip(before['weights'],after['weights'])):
        changed_names={n for n in a.keys()|b.keys() if abs(a.get(n,0)-b.get(n,0))>1e-6}
        if any(n.startswith('袖環') for n in b):generated.append(index)
        if not changed_names:continue
        changed.append(index)
        if not all(n.startswith(('腕','袖環')) for n in changed_names):unsupported.append(index)
    if unsupported:failures.append('Non-arm weights changed')
    if set(changed)!=set(generated):failures.append('Weight changes differ from generated cuff domain')
    report={'passed':not failures,'unchanged':unchanged,'vertices':len(after['weights']),
            'morph_count':len(after['morphs'])-1,'changed_weight_vertices':len(changed),
            'generated_weight_vertices':len(generated),'unsupported_weight_vertices':unsupported,
            'weight_comparison_tolerance':1e-6,'failures':failures,
            'uv_details':uv_details,
            'documented_hand_uv_change_only':uv_exception,
            'scope':'index-preserving PMX comparison: geometry/morph arrays exact, weights tolerance 1e-6; UV equality reported separately, optional documented glove UV fix; not dynamic acceptance'}
    write_json(out,report);print('CUFF_MESH_REVIEW',report,flush=True)
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
