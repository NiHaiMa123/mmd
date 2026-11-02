"""Open the verified complete project through Blender MCP after all jobs exit."""
import bpy,json
from pathlib import Path
P=Path(r'E:\project\mmd\work\headswap_xl_codex\native_mmd_bridge_20261030\headless_bullet');OUT=P/'FINAL_MMD15'
report=json.loads((OUT/'delivery_report.json').read_text('utf8'));assert report['status']=='COMPLETE_NEW_NORMAL_MMD15_VIDEO_BLEND_CACHES_AND_REPRO_VERIFIED'
job=bpy.app.driver_namespace.get('MMD_BACKGROUND_finish_delivery_final');assert job is None or job.poll()==0,'Delivery job has not successfully exited'
def show():
    if bpy.data.is_dirty:bpy.ops.wm.save_as_mainfile(filepath=str(P/'mcp_review_state_before_final_open.blend'),copy=True,compress=True,relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=report['blend'],load_ui=False,use_scripts=False)
    bpy.context.scene.frame_set(1)
    return None
bpy.app.timers.register(show,first_interval=.2);print(json.dumps(dict(verified_delivery=report['video'],opening_complete_project=report['blend'],input_control='none'),ensure_ascii=False))
