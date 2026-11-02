import sys,json
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import regions,coords
engine('import_export').ensure_mmd_tools();base=ROOT.parent/'work/headswap_xl_codex/contact_repair_20261028';env=json.loads((base/'hair_arm_feedback_20261028/root_contact_diagnosis.json').read_text('utf8'));p=json.loads((base/'body_track/rig_profile.json').read_text('utf8'));bpy.ops.wm.open_mainfile(filepath=str(base/'body_track/BodyContact_UpperBodyCandidate.blend'),load_ui=False,use_scripts=False);mesh=bpy.data.objects[p['mesh']];arm=bpy.data.objects[p['armature']];parts=regions(mesh,arm,p);rows=[]
for f in (216,218,220):
 bpy.context.scene.frame_set(f);bpy.context.view_layer.update();co=coords(mesh);m=np.array(arm.matrix_world@arm.pose.bones['頭'].matrix);delta=m@np.linalg.inv(env['anchor_bind_matrix']);point=np.asarray(env['guide'][0])@delta[:3,:3].T+delta[:3,3];tree=BVHTree.FromPolygons(co.tolist(),parts['faces']['head'],all_triangles=True);q,n,fi,d=tree.find_nearest(Vector(point));outward=(point-np.array(q))/d;chain=[arm.pose.bones[n] for n in p['control_chains'][1]];h=np.array(arm.matrix_world@chain[0].head);e=np.array(arm.matrix_world@chain[1].head);w=np.array(arm.matrix_world@chain[2].head);row={'frame':f,'root':point.tolist(),'head_outward':outward.tolist(),'reach_m':float(np.linalg.norm(w-h)),'arm_length_m':float(np.linalg.norm(h-e)+np.linalg.norm(e-w)),'wrist':w.tolist(),'head_rotation':m[:3,:3].tolist()};rows.append(row);print('ROOT_DETOUR',json.dumps(row),flush=True)
(base/'hair_arm_feedback_20261028/detour_directions.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
