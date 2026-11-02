import bpy,json,numpy as np
from pathlib import Path
root=Path(r'E:\project\mmd\work\headswap_xl_codex\jiggle_physics_20261031')
source=root/'candidate09/完整角色_Jiggle配置_未烘焙.blend'
frames=[1,69,175,242,256,310,331,450];results=[]
for method in [1,2,3]:
 bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False,load_ui=False)
 arm=bpy.data.objects['东雪莲x达妮娅_骨架'];s=bpy.context.scene
 names=['頭','上半身3','右腕','左腕','右手首','左手首','左足D']
 names=[n for n in names if n in arm.pose.bones];before={}
 for f in frames:
  s.frame_set(f);bpy.context.view_layer.update();before[f]=np.array([np.array(arm.pose.bones[n].matrix) for n in names])
 strips=[]
 for track in arm.animation_data.nla_tracks:
  for strip in track.strips:
   old={k:getattr(strip,k) for k in ['frame_start','frame_end','action_frame_start','action_frame_end','scale','blend_in','blend_out']}
   if method==1:strip.frame_start=1+(old['frame_start']-1)*4;strip.scale=old['scale']*4
   if method==2:strip.scale=old['scale']*4;strip.frame_start_ui=1+(old['frame_start']-1)*4
   if method==3:
    strip.frame_start_raw=1+(old['frame_start']-1)*4;strip.frame_end_raw=1+(old['frame_end']-1)*4;strip.scale=old['scale']*4
   strip.blend_in=old['blend_in']*4;strip.blend_out=old['blend_out']*4
   for fc in strip.fcurves:
    for pt in fc.keyframe_points:
     pt.co.x=1+(pt.co.x-1)*4;pt.handle_left.x=1+(pt.handle_left.x-1)*4;pt.handle_right.x=1+(pt.handle_right.x-1)*4
    fc.update()
   strips.append(dict(name=strip.name,old=old,new={k:getattr(strip,k) for k in old}))
 errors=[]
 for f in frames:
  s.frame_set(1+(f-1)*4);bpy.context.view_layer.update();after=np.array([np.array(arm.pose.bones[n].matrix) for n in names]);errors.append(dict(frame=f,error=float(np.abs(before[f]-after).max())))
 results.append(dict(method=method,strips=strips,errors=errors));print('RETIME',method,errors,flush=True)
(root/'retime_checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
