"""Open the repair in a new interactive Blender, frame it and start local MCP."""
import sys
from pathlib import Path
import bpy,addon_utils
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
engine('import_export').ensure_mmd_tools()
filename=Path(sys.argv[sys.argv.index('--')+1]).resolve();bpy.ops.wm.open_mainfile(filepath=str(filename),load_ui=True,use_scripts=False)
from mathutils import Vector

def frame_view():
    # Loading saved UI finishes after open_mainfile returns in a startup script.
    # Configure its final spaces on the next event-loop tick.
    body=bpy.data.objects['达妮娅_mesh'];evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    points=[body.matrix_world@v.co for v in mesh.vertices];low=Vector(tuple(min(p[k] for p in points) for k in range(3)));high=Vector(tuple(max(p[k] for p in points) for k in range(3)));evaluated.to_mesh_clear()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type!='VIEW_3D':continue
            space=area.spaces.active;space.overlay.show_overlays=False;space.show_gizmo=False;space.show_region_ui=False;space.show_region_toolbar=False;space.shading.type='MATERIAL';space.shading.use_scene_lights=False;space.shading.use_scene_world=False;space.clip_start=.001
            space.region_3d.view_rotation=Vector((.12,-1,.025)).to_track_quat('Z','Y');space.region_3d.view_perspective='ORTHO'
            space.region_3d.view_location=(low+high)*.5
            space.region_3d.view_distance=(high.z-low.z)*1.5
    bpy.ops.wm.save_as_mainfile(filepath=str(filename),compress=True)
    print('NATIVE_REPAIR_UI_READY',filename,flush=True)

model=engine('import_export').model_meshes(list(bpy.context.scene.objects))
for o in bpy.context.scene.objects:o.hide_set(o not in model);o.select_set(o in model)
bpy.context.view_layer.objects.active=bpy.data.objects['达妮娅_mesh']
for o in model:o.select_set(False)
bpy.context.view_layer.objects.active=None
if not hasattr(bpy.context.scene,'blendermcp_port'):addon_utils.enable('blender_mcp',default_set=False)
if not getattr(getattr(bpy.types,'blendermcp_server',None),'running',False):bpy.ops.blendermcp.start_server()
bpy.app.timers.register(frame_view,first_interval=.5)
