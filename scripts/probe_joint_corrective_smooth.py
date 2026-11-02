import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,audit_frame,coords
engine('import_export').ensure_mmd_tools();root=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';out=root/'joint_diagnosis'
bpy.ops.wm.open_mainfile(filepath=str(root/'body_track/BodyContact_FinalCandidate.blend'),load_ui=False,use_scripts=False)
p=json.loads((root/'body_track/rig_profile.json').read_text('utf8'));mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p)
centres=[arm.matrix_world@arm.data.bones[n].head_local for n in ('左足','右足')];ids=set(i for r in ('leg.L','leg.R','torso') for i in parts['ids'][r]);group=mesh.vertex_groups.new(name='Contact: hip corrective mask')
for i in ids:
 pos=mesh.matrix_world@mesh.data.vertices[i].co;d=min((pos-c).length for c in centres);weight=math.exp(-.5*(d/.075)**2)
 if d<.16:group.add([i],weight,'REPLACE')
mod=mesh.modifiers.new('Hip joint corrective experiment','CORRECTIVE_SMOOTH');mod.vertex_group=group.name;mod.rest_source='ORCO';mod.smooth_type='LENGTH_WEIGHTED';mod.use_pin_boundary=False;rows=[]
for f in (220,240,260,320,361,450):
 bpy.context.scene.frame_set(f);mod.show_viewport=False;bpy.context.view_layer.update();base=coords(mesh)
 for factor,repeat in ((.5,5),(.7,10),(1.,15)):
  mod.factor=factor;mod.iterations=repeat;mod.show_viewport=True;bpy.context.view_layer.update();co=coords(mesh);a=audit_frame(mesh,arm,p,parts,hair=False,cap=2000)
  r={'frame':f,'factor':factor,'iterations':repeat,'leg_crossings':sum(r['triangle_crossings'] for r in a['pairs'] if r['pair'][0].startswith('leg')),'max_delta_m':float(np.linalg.norm(co-base,axis=1).max())};rows.append(r);print('HIP_CORRECTIVE_PROBE',r,flush=True)
(out/'hip_corrective_smooth_probes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
