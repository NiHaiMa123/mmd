import sys,json
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame
from animation_contact_tools.projector import FrameProjector
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);mods=[m for m in mesh.modifiers if m.type=='ARMATURE'];rows=[]
for f in (1,220,240,361,420):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
 for dq in (False,True):
  for mod in mods:mod.use_deform_preserve_volume=dq
  bpy.context.view_layer.update();audit=audit_frame(mesh,arm,p,parts,hair=False,cap=2000);row={'frame':f,'dual_quaternion':dq,'pairs':[{'pair':r['pair'],'crossings':r['triangle_crossings']} for r in audit['pairs'] if r['triangle_crossings']]};rows.append(row);print('DQ_PROBE',row,flush=True)
for mod in mods:mod.use_deform_preserve_volume=False
p['preserve_wrist_orientation']=False
for f in (1,180,240,420):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();solver=FrameProjector(mesh,arm,p,parts,p['control_chains'],limit_degrees=30);solver.capture();x,result=solver.solve(iterations=40);rows.append({'frame':f,'free_wrist_projection':result});print('WRIST_PROBE',f,result['remaining_crossings'],result['max_control_delta_deg'],flush=True)
(out/'joint_skinning_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
