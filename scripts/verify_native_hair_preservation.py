"""Compare native source data without evaluating or changing simulation caches."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);engine('import_export').ensure_mmd_tools()
def load(path,names):
    with bpy.data.libraries.load(path,link=False) as (available,target):target.objects=names
    return target.objects
def key_hashes(obj,subset=None):
    result={}
    for key in obj.data.shape_keys.key_blocks:
        co=np.empty(len(key.data)*3,np.float32);key.data.foreach_get('co',co);co=co.reshape(-1,3)
        if subset is not None:co=co[subset]
        result[key.name]=hashlib.sha256(co.tobytes()).hexdigest()
    return result
def weight_hash(obj,indices=None):
    bones={b.name for b in obj.find_armature().data.bones} if obj.find_armature() else set()
    names={g.index:g.name for g in obj.vertex_groups};h=hashlib.sha256()
    for i in indices if indices is not None else range(len(obj.data.vertices)):
        weights=sorted((names[g.group],g.weight) for g in obj.data.vertices[int(i)].groups if names[g.group] in bones)
        h.update(json.dumps(weights,ensure_ascii=False,separators=(',',':')).encode('utf8'))
    return h.hexdigest()
def curves_hash(action):
    rows=[]
    for layer in action.layers:
        for strip in layer.strips:
            for bag in getattr(strip,'channelbags',[]):
                for curve in bag.fcurves:
                    co=np.array([[*p.co,*p.handle_left,*p.handle_right] for p in curve.keyframe_points],np.float32)
                    rows.append((curve.data_path,curve.array_index,hashlib.sha256(co.tobytes()).hexdigest()))
    return hashlib.sha256(json.dumps(sorted(rows),ensure_ascii=False).encode('utf8')).hexdigest()
source=load(a.source,['东雪莲x达妮娅_素体'])[0];candidate,hair=load(a.candidate,['东雪莲x达妮娅_素体','完整头发_原生Cloth_实际发片'])
origin=np.array([v.value for v in hair.data.attributes['SourceVertexID'].data],np.int32)
source_keys=key_hashes(source);candidate_keys=key_hashes(candidate);hair_keys=key_hashes(hair);source_subset=key_hashes(source,origin)
assert source_keys==candidate_keys,'Original shape-key data changed'
assert source_subset==hair_keys,'Hair shape-key data changed beyond topology-preserving subset'
source_weights=weight_hash(source);candidate_weights=weight_hash(candidate)
assert source_weights==candidate_weights,'Original bone weights changed'
src_arm=source.find_armature();dst_arm=candidate.find_armature();nla=[]
for left,right in zip(src_arm.animation_data.nla_tracks,dst_arm.animation_data.nla_tracks):
    assert left.name==right.name
    for ss,ts in zip(left.strips,right.strips):
        assert curves_hash(ss.action)==curves_hash(ts.action),'Original NLA action curves changed'
        assert (ss.frame_start,ss.frame_end,ss.blend_type,ss.influence)==(ts.frame_start,ts.frame_end,ts.blend_type,ts.influence)
        nla.append(dict(track=left.name,action_hash=curves_hash(ss.action)))
report=dict(status='ORIGINAL_SHAPE_KEYS_WEIGHTS_AND_NLA_CURVES_PRESERVED',source=a.source,candidate=a.candidate,original_shape_keys=len(source_keys),hair_shape_keys=len(hair_keys),hair_vertices=len(origin),source_weight_hash=source_weights,candidate_weight_hash=candidate_weights,nla=nla,scope='Raw native data only; dynamic geometry and visual quality are audited separately')
Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
