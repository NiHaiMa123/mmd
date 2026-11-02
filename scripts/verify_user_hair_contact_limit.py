"""Replay measured real-scene examples against the user's 5 cm rule."""
import bpy,sys,json,numpy as np
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
from animation_contact_tools.hair_contact_threshold import embedded_patch_metrics
engine('import_export').ensure_mmd_tools();base=repo.parent/'work/headswap_xl_codex';out=base/'native_solid_contact_20261101/user_5cm_policy';out.mkdir(exist_ok=True)
d=np.load(base/'standard_proxy_20261031/inspection/inputs.npz');old=base/'short_sidehair_20261101/revision02_exact_body';native=base/'native_solid_contact_20261101/side_rods01_failure_replay';rows=[]
cases=[('previous_whole_lock_intrusion',json.loads((old/'setup.json').read_text('utf8'))['blend'],226,base/'short_sidehair_20261101/user_75s_125s_measurement/frame_226_signed_distances.npz',True),('previous_both_locks_intrusion',json.loads((old/'setup.json').read_text('utf8'))['blend'],376,base/'short_sidehair_20261101/user_75s_125s_measurement/frame_376_signed_distances.npz',True),('current_small_tip_contact',str(native/'完整角色_失败现场_仅1至7秒.blend'),211,native/'full_measure/frame_211_signed_distances.npz',False)]
for name,source,frame,measured,expected in cases:
 bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False);bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();co=coords(bpy.data.objects['东雪莲x达妮娅_素体']);z=np.load(measured);assert np.array_equal(z['hair_ids'],d['ids'])
 m=embedded_patch_metrics(co[d['ids']],z['vertex_signed_distance_m'],d['edges'],limit_m=.05)
 row=dict(case=name,frame=frame,original_seconds=(frame-1)/30,maximum_depth_cm=m['maximum_depth_m']*100,maximum_connected_patch_extent_cm=m['maximum_patch_extent_m']*100,exceeds_5cm=m['exceeds_limit'],expected_exceeds_5cm=expected,inside_vertices=m['inside_vertices']);rows.append(row)
 assert m['exceeds_limit']==expected,row
report=dict(status='USER_5CM_POLICY_REPLAYS_REAL_CASES_CORRECTLY',rule='Strictly greater than 5 cm in either maximum inward depth or maximum Euclidean span of one connected embedded patch',rows=rows,physics_started=False,zero_collision_claim=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
