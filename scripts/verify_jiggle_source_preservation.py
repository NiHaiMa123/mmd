"""Verify original shape keys, actions and the explicitly recorded rig edits."""
import argparse,hashlib,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.candidate)
config=json.loads((out/'configuration.json').read_text('utf8'));report=json.loads((out/'bake_report.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools()
def load(path):
 with bpy.data.libraries.load(path,link=False) as (available,target):target.objects=['东雪莲x达妮娅_素体']
 return target.objects[0]
def keys(obj):
 result={}
 for key in obj.data.shape_keys.key_blocks:
  data=np.empty(len(key.data)*3,np.float32);key.data.foreach_get('co',data)
  result[key.name]=hashlib.sha256(data.tobytes()).hexdigest()
 return result
def curves(action):
 result=[]
 for layer in action.layers:
  for strip in layer.strips:
   for bag in getattr(strip,'channelbags',[]):
    for fc in bag.fcurves:
     data=np.array([[*pt.co,*pt.handle_left,*pt.handle_right] for pt in fc.keyframe_points],np.float32)
     result.append((fc.data_path,fc.array_index,hashlib.sha256(data.tobytes()).hexdigest()))
 return sorted(result)
def weights(obj,i):return {obj.vertex_groups[g.group].name:float(g.weight) for g in obj.data.vertices[i].groups}
source=load(config['source']);candidate=load(report['blend']);left=keys(source);right=keys(candidate)
assert all(right.get(n)==v for n,v in left.items()),'Original shape keys changed'
edits={int(row['vertex']):row for row in config['head_attachment_weight_edits']};changed=[]
for i in range(len(source.data.vertices)):
 sw=weights(source,i);cw=weights(candidate,i)
 if sw!=cw:
  assert i in edits,('Unrecorded weight edit',i)
  assert cw.get('頭')==1.,('Invalid attachment edit',i)
  for name,w in sw.items():
   if name not in edits[i]['old']:assert cw.get(name)==w,('Unrelated group changed',i,name)
  changed.append(i)
assert set(changed)==set(edits)
sa=source.find_armature();ca=candidate.find_armature();assert len(sa.animation_data.nla_tracks)==len(ca.animation_data.nla_tracks)
actions=[]
for st,ct in zip(sa.animation_data.nla_tracks,ca.animation_data.nla_tracks):
 assert st.name==ct.name and len(st.strips)==len(ct.strips)
 for ss,cs in zip(st.strips,ct.strips):
  assert curves(ss.action)==curves(cs.action),('Original action changed',st.name)
  for key in ['frame_start','frame_end','scale','action_frame_start','action_frame_end','blend_type','influence']:
   assert getattr(ss,key)==getattr(cs,key),(st.name,key)
  actions.append(st.name)
result=dict(status='PASS_ORIGINAL_DATA_AND_DECLARED_ATTACHMENT_EDITS',original_shape_keys=len(left),added_shape_keys=sorted(set(right)-set(left)),recorded_attachment_vertices=len(changed),unchanged_other_weight_vertices=len(source.data.vertices)-len(changed),original_nla_tracks=actions,scope='Raw source data only. Dynamic motion, surface contact and visual quality require separate review.')
(out/'source_preservation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print(json.dumps(result,ensure_ascii=False),flush=True)
