"""Export the calibrated whole-head model through the user's live Blender MCP."""
import bpy,sys,importlib,json,traceback
from pathlib import Path
P=Path(r'E:\project\mmd\work\headswap_xl_codex\native_mmd_bridge_20261030')
OUT=P/'headless_bullet/input';OUT.mkdir(parents=True,exist_ok=True)
state=bpy.app.driver_namespace['MMD_CALIBRATED_NATIVE_CHAIN_20261030']
def export():
    try:
        scene=bpy.data.scenes[state['scene']];root=bpy.data.objects[state['root']];arm=bpy.data.objects[state['armature']]
        assert bpy.context.scene==scene
        scene.rigidbody_world.enabled=False;scene.frame_set(1);bpy.context.view_layer.update()
        module=next(m for n,m in sys.modules.items() if n=='mmd_tools' or n.endswith('.mmd_tools'))
        importlib.import_module(module.__name__+'.core.model').Model(root).clean()
        scene.frame_start=1;scene.frame_end=480
        for o in bpy.context.selected_objects:o.select_set(False)
        root.select_set(True);bpy.context.view_layer.objects.active=root
        assert not (OUT/'character_calibrated.pmx').exists(),'Do not overwrite an existing export'
        bpy.ops.mmd_tools.export_pmx(filepath=str(OUT/'character_calibrated.pmx'),scale=1,copy_textures_mode='NONE',visible_meshes_only=True,fix_bone_order=True)
        root.select_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm
        bpy.ops.mmd_tools.export_vmd(filepath=str(OUT/'corrected_body_fk.vmd'),scale=1,use_frame_range=True,preserve_curves=True,use_pose_mode=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'headless_source.blend'),compress=True)
        report=dict(stage='EXPORTED',scene=scene.name,armature=arm.name,world_enabled=scene.rigidbody_world.enabled,frames=480,preroll=30,scale=1,files={p.name:p.stat().st_size for p in OUT.iterdir() if p.is_file()})
    except BaseException as exc:report=dict(stage='FAILED',error=repr(exc),traceback=traceback.format_exc())
    (OUT/'export_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    return None
bpy.app.timers.register(export,first_interval=.1)
print(json.dumps(dict(queued=True,status=str(OUT/'export_status.json'))))
