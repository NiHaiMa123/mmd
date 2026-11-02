import bpy,json
from pathlib import Path
P=Path(r'E:\project\mmd\work\headswap_xl_codex\native_mmd_bridge_20261030\headless_bullet\FINAL_MMD15')
assert Path(bpy.data.filepath).resolve()==(P/'完整角色_整头连续物理_15秒.blend').resolve()
print(json.dumps(dict(final_project_open=True,filepath=bpy.data.filepath,frame=bpy.context.scene.frame_current,frame_end=bpy.context.scene.frame_end,fps=bpy.context.scene.render.fps,resolution=[bpy.context.scene.render.resolution_x,bpy.context.scene.render.resolution_y]),ensure_ascii=True))
