import sys,json,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
from animation_contact_tools.hair_projector import HairProjector
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'hair_projection_probe';out.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_Adaptive.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
solver=HairProjector(mesh,arm,p,parts,limit_degrees=30,max_active=15);solver.capture();before=audit_frame(mesh,arm,p,parts,hair=True,cap=2000);co=coords(mesh);skin=sorted(set(parts['ids']['torso']+parts['ids']['head']+parts['ids']['hand.L']+parts['ids']['hand.R']))
protected=co[skin].copy();rest=np.array([v.co[:] for v in mesh.data.vertices]);edges=np.array([[e.vertices[0],e.vertices[1]] for e in mesh.data.edges if all(i in set(parts['ids']['hair_mobile']) for i in e.vertices)]) if False else None
hairids=set(parts['ids']['hair_mobile']);edges=np.array([e.vertices[:] for e in mesh.data.edges if all(i in hairids for i in e.vertices)]);length=np.linalg.norm(co[edges[:,0]]-co[edges[:,1]],axis=1);valid=length>.0001
t=time.monotonic();x,result=solver.solve(iterations=35);after=coords(mesh);ratio=np.linalg.norm(after[edges[:,0]]-after[edges[:,1]],axis=1)[valid]/length[valid]
result.update(before_crossings=sum(r['triangle_crossings'] for r in before['pairs'] if r['pair'][0].startswith('hair')),body_max_error_m=float(np.max(np.abs(after[skin]-protected))),edge_ratio_p99=float(np.percentile(ratio,99)),edge_ratio_max=float(ratio.max()),eligible_bones=[b.name for b in solver.bones],seconds=time.monotonic()-t)
(out/'probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print('HAIR_PROJECTION_RESULT',json.dumps(result,ensure_ascii=False),flush=True)
# Freeze corrected channels in a distinct action for review, no original edits.
delta=bpy.data.actions.new('ExperimentalHairPose_F1_NotAccepted');arm.animation_data.use_nla=False;arm.animation_data.action=delta
for b in solver.bones:b.keyframe_insert('rotation_quaternion',frame=1)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'HairProjection_F1_NotAccepted.blend'),compress=True)
