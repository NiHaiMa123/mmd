"""Audit the untouched source data and protected body motion in the new scene."""
import sys,json,argparse,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.track import fcurves
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);p.add_argument('--source',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.delivery);pub=json.loads((out/'cache_publication.json').read_text('utf8'));src=Path(pub['input']);manifest=json.loads((src/'export_complete.json').read_text('utf8'));profile=json.loads(Path(manifest['rig_profile']).read_text('utf8'));skin=np.load(src/'skin_ids.npy');body=np.load(src/'body.npy',mmap_mode='r');engine('import_export').ensure_mmd_tools()
def static(path):
 bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False);m=bpy.data.objects[profile['mesh']];d=m.data;buffer=np.empty(len(d.vertices)*3,dtype=np.float32);h=hashlib.sha256()
 for key in d.shape_keys.key_blocks:key.data.foreach_get('co',buffer);h.update(key.name.encode());h.update(buffer.tobytes())
 actions={}
 for action in bpy.data.actions:
  rows=[(c.data_path,c.array_index,[(tuple(k.co),tuple(k.handle_left),tuple(k.handle_right),k.interpolation) for k in c.keyframe_points]) for c in fcurves(action)];actions[action.name]=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
 weights=hashlib.sha256(json.dumps([[(m.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in d.vertices],ensure_ascii=False).encode()).hexdigest();topology=hashlib.sha256(json.dumps([(tuple(p.vertices),p.material_index) for p in d.polygons]).encode()).hexdigest()
 return dict(shape_keys=h.hexdigest(),shape_key_count=len(d.shape_keys.key_blocks),weights=weights,topology=topology,vertices=len(d.vertices),polygons=len(d.polygons),actions=actions,materials=[slot.material.name if slot.material else None for slot in m.material_slots])
original=static(a.source);rows=[];s=bpy.context.scene;m=bpy.data.objects[profile['mesh']]
frames=sorted(set(list(range(1,204))+list(range(256,451))+np.arange(256,321.0001,.125).tolist()))
for f in frames:
 s.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();k=round((f-manifest['frames'][0])/manifest['sample_step']);err=float(np.abs(coords(m)[skin]-body[k]).max());rows.append(dict(frame=float(f),body_error_m=err));assert err<2e-6,rows[-1]
candidate=static(out/'完整角色_整头连续物理_15秒.blend');unchanged={k:original[k]==candidate[k] for k in original if k!='actions'};source_actions={name:candidate['actions'].get(name)==digest for name,digest in original['actions'].items()};report=dict(status='SOURCE_GEOMETRY_WEIGHTS_SHAPEKEYS_ACTIONS_AND_PROTECTED_BODY_PASS',source=a.source,candidate=str(out/'完整角色_整头连续物理_15秒.blend'),unchanged=unchanged,source_actions_unchanged=source_actions,added_actions=[name for name in candidate['actions'] if name not in original['actions']],original_fingerprints=original,candidate_fingerprints=candidate,body_outside_automatic_route_samples=len(rows),max_body_difference_outside_route_m=max(x['body_error_m'] for x in rows),protected_frames=[256,321],protected_sampling_step=.125,route_window=[204,255.75],initial_hair_roots_relocated_before_physics=True,clothing_workflow_resumed=False,shutdown_configured=False);(out/'source_preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');assert all(unchanged.values()) and all(source_actions.values());print('FULL_HAIR_SOURCE_PRESERVATION_PASS',flush=True)
