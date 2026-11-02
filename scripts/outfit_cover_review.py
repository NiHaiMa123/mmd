"""Verify the actual glove backup against original target geometry and morphs."""
import argparse
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
parser=argparse.ArgumentParser(); parser.add_argument('--job',required=True); parser.add_argument('--out',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
job=Path(args.job)
result,profile=read_json(job/'result.json'),read_json(job/'profile_snapshot.json')
coverage=next(p['skin_coverage'] for p in result['adaptations']['patches'] if p['region']=='hands')
ie=engine('import_export'); ie.ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=result['blend'])
backup=bpy.data.objects[coverage['backup_object']]
assert backup.parent is None and backup.hide_render and backup.hide_get()
assert backup not in ie.model_meshes()
assert len(backup.data.polygons)==coverage['masked_skin_faces']
def weights(obj,i):
    return tuple(sorted((obj.vertex_groups[g.group].name,round(g.weight,6)) for g in obj.data.vertices[i].groups
                        if round(g.weight,6)>0 and not obj.vertex_groups[g.group].name.startswith('mmd_')))
def vertex_uv(obj):
    uv=obj.data.uv_layers.active; result={}
    for loop in obj.data.loops:
        result.setdefault(loop.vertex_index,tuple(uv.data[loop.index].uv))
    return result
positions=[v.co.copy() for v in backup.data.vertices]
weight_rows=[weights(backup,i) for i in range(len(positions))]
uv_rows=vertex_uv(backup)
keys={}
for key in backup.data.shape_keys.key_blocks:
    values=np.empty(len(positions)*3,dtype=np.float32); key.data.foreach_get('co',values)
    keys[key.name]=values.reshape(-1,3)
report={'coverage':coverage,'backup_outside_export':True,'backup_vertices':len(positions),
        'backup_faces':len(backup.data.polygons),'backup_shape_keys':len(keys)}
ie.clear_scene(); target=ie.import_pmx(profile['target']['path']); body=ie.model_meshes(target)[0]
tree=KDTree(len(body.data.vertices))
for v in body.data.vertices: tree.insert(v.co,v.index)
tree.balance()
target_uv=vertex_uv(body)
lift=profile.get('shoe_fit',{}).get('body_lift',0)
mapping=[]
for i,point in enumerate(positions):
    nearby=tree.find_range(point-Vector((0,0,lift)),1e-6)
    candidates=nearby
    candidates=[(d,j) for p,j,d in candidates if weights(body,j)==weight_rows[i]
                and max(abs(a-b) for a,b in zip(target_uv[j],uv_rows[i]))<1e-6]
    if not candidates:
        print('BACKUP_MISMATCH',{'vertex':i,'position':list(point),'weights':weight_rows[i],'uv':uv_rows[i],
            'nearby':[{'index':j,'distance':d,'weights':weights(body,j),'uv':target_uv[j]} for p,j,d in nearby]},flush=True)
        raise AssertionError(f'Backup vertex {i} does not match original target position/UV/weights')
    mapping.append(min(candidates)[1])
errors={}
for name,values in keys.items():
    key=body.data.shape_keys.key_blocks.get(name)
    if key is None: raise AssertionError('Missing original target shape key '+name)
    original=np.empty(len(body.data.vertices)*3,dtype=np.float32); key.data.foreach_get('co',original)
    expected=original.reshape(-1,3)[mapping].copy(); expected[:,2]+=lift
    errors[name]=float(np.max(np.linalg.norm(values-expected,axis=1)))
assert max(errors.values(),default=0)<1e-6,errors
report.update(original_vertex_matches=len(mapping),uv_and_weights_match=True,
              weight_precision='6 decimal places, matching existing subset copier; zero-quantized weights ignored',
              all_target_morphs_match=True,max_morph_error_m=max(errors.values(),default=0),
              morph_errors=errors)
out=Path(args.out); out.mkdir(parents=True,exist_ok=True); write_json(out/'report.json',report)
print('COVER_REVIEW', {k:v for k,v in report.items() if k not in {'morph_errors','coverage'}},flush=True)
