"""Open the cached white-room trial with its supplied camera and local MCP."""
import sys,socket,json
from pathlib import Path
import bpy,addon_utils
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();filename=Path(sys.argv[sys.argv.index('--')+1]).resolve();bpy.ops.wm.open_mainfile(filepath=str(filename),load_ui=True,use_scripts=False)
def ready():
    scene=bpy.context.scene;scene.frame_set(int(scene.get('outfit_preview_first',1)));model=set(ie.model_meshes())
    for o in scene.objects:
        o.hide_set(o not in model and o.name!='WhiteWall' and o.type not in {'CAMERA','LIGHT'});o.select_set(False)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type!='VIEW_3D':continue
            s=area.spaces.active;s.overlay.show_overlays=False;s.show_gizmo=False;s.show_region_ui=False;s.show_region_toolbar=False;s.shading.type='MATERIAL';s.shading.use_scene_world=True;s.shading.use_scene_lights=True;s.region_3d.view_perspective='CAMERA';s.region_3d.view_camera_zoom=0;s.clip_start=.001
    bpy.context.view_layer.objects.active=None
    if not hasattr(scene,'blendermcp_port'):addon_utils.enable('blender_mcp',default_set=False)
    if not getattr(getattr(bpy.types,'blendermcp_server',None),'running',False):
        for port in range(9876,9887):
            try:
                with socket.socket() as probe:probe.bind(('127.0.0.1',port))
            except OSError:continue
            scene.blendermcp_port=port;break
        else:raise RuntimeError('No free local Blender MCP port')
        bpy.ops.blendermcp.start_server()
    (filename.parent/'ui_session.json').write_text(json.dumps({'file':str(filename),'mcp_port':scene.blendermcp_port}),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(filename),compress=True);print('CYNICAL_PREVIEW_UI_READY',flush=True)
bpy.app.timers.register(ready,first_interval=.5)
