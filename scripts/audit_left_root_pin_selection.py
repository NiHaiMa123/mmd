"""Separate rig-rigid attachment vertices from heuristic guide-root pins."""
import sys,json
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.exact_skin_collider import build_exact_skin_topology
from animation_contact_tools.closed_collider_field import ClosedColliderField
root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261029/multi_bundle';directory=root/'left_arm_feedback_refined';source=json.loads((directory/'source.json').read_text('utf8'))['source'];profile=json.loads((directory/'profile.json').read_text('utf8'));envelope=json.loads((directory/'envelope.json').read_text('utf8'));initial=np.load(root/'left_native/initial_projection.npz');ids=initial['ids'];points=initial['coordinates'];pinned=initial['pinned'];bind=np.asarray(envelope['anchor_bind_matrix']);engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);mesh=bpy.data.objects[profile['mesh']];arm=bpy.data.objects[profile['armature']];group=mesh.vertex_groups[envelope['anchor_bone']].index;weights=np.array([sum(g.weight for g in mesh.data.vertices[int(i)].groups if g.group==group) for i in ids]);skin_ids,skin_faces,meta=build_exact_skin_topology(mesh,arm,profile);rows=[]
for f in (1,241,242,243,243.5,244,245,246,247,248):
 bpy.context.scene.frame_set(int(f),subframe=f%1);bpy.context.view_layer.update();co=coords(mesh);delta=np.array(arm.matrix_world@arm.pose.bones[envelope['anchor_bone']].matrix)@np.linalg.inv(bind);world=points@delta[:3,:3].T+delta[:3,3];field=ClosedColliderField(co[skin_ids],skin_faces);d,_=field(world);groups={}
 for label,mask in [('guide_pins',pinned),('rig_rigid',weights>.999),('rig_ge_08',weights>=.8),('extra_guide_pins',pinned&(weights<.8)),('rig_rigid_outside_guide',(weights>.999)&~pinned)]:
  groups[label]={'count':int(mask.sum()),'inside_count':int((d[mask]<0).sum()),'min_distance_m':float(d[mask].min()) if mask.any() else None}
 rows.append({'frame':f,'groups':groups});print('ROOT_PIN_SELECTION',f,json.dumps(groups),flush=True)
np.savez_compressed(root/'left_root_pin_audit.npz',ids=ids,head_weights=weights,heuristic_pinned=pinned,rig_rigid=weights>.999);(root/'left_root_pin_audit.json').write_text(json.dumps({'source':source,'anchor':envelope['anchor_bone'],'rows':rows},ensure_ascii=False,indent=2),encoding='utf8')
