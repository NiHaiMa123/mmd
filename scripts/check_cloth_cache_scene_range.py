import bpy,json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
engine('import_export').ensure_mmd_tools();p=ROOT.parent/'work/headswap_xl_codex/standard_cloth_20261031/candidate06'
rows=[]
for first in [1,-59]:
 bpy.ops.wm.open_mainfile(filepath=str(p/'完整角色_原生发片Cloth_15秒.blend'),load_ui=False,use_scripts=False)
 s=bpy.context.scene;s.frame_start=first;h=bpy.data.objects['完整头发_原生Cloth_实际发片'];arm=bpy.data.objects['东雪莲x达妮娅_骨架'];cl=next(m for m in h.modifiers if m.type=='CLOTH');pc=cl.point_cache
 g=h.vertex_groups[cl.settings.vertex_group_mass].index;weights=[sum(x.weight for x in v.groups if x.group==g) for v in h.data.vertices]
 s.frame_set(1);bpy.context.view_layer.update();x=coords(h);mat=np.linalg.inv(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix));ref=x@mat[:3,:3].T+mat[:3,3]
 s.frame_set(69);bpy.context.view_layer.update();x=coords(h);mat=np.linalg.inv(np.array(arm.matrix_world@arm.pose.bones['頭'].matrix));co=x@mat[:3,:3].T+mat[:3,3]
 r=dict(scene_start=first,cache_start=pc.frame_start,cache_end=pc.frame_end,baked=pc.is_baked,outdated=pc.is_outdated,info=pc.info,pinned=sum(w>.99 for w in weights),viewport=cl.show_viewport,render=cl.show_render,motion_p95=float(np.quantile(np.linalg.norm(co-ref,axis=1),.95)))
 rows.append(r);print(json.dumps(r),flush=True)
(p/'scene_range_cache_probe.json').write_text(json.dumps(rows,indent=2),'utf8')
