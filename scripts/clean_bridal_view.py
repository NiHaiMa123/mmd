"""Run in the live Blender MCP session: display the outfit without helpers.

Visibility-only changes; save a new clean-view copy, keeping all rig data.
"""
import bpy,json
from pathlib import Path
from datetime import datetime
from mathutils import Vector

directory=Path(r'E:\project\mmd\mmd_repo\outputs\white_bridal_shoes\final')
if Path(bpy.data.filepath).parent.resolve()!=directory.resolve():
    raise RuntimeError('The live Blender file is not the bridal-shoe outfit')
shoes=[o for o in bpy.context.scene.objects if o.get('external_shoe')]
arms={o.parent for o in shoes if o.parent and o.parent.type=='ARMATURE'}
if len(arms)!=1 or len(shoes)!=20:raise RuntimeError('Cannot identify the unique fitted shoe assembly')
arm=next(iter(arms))
model=[o for o in arm.children_recursive if o.type=='MESH' and not o.get('outfit_backup') and getattr(o,'mmd_type','NONE')=='NONE']
if len(model)!=22:raise RuntimeError('Unexpected character mesh layout; refusing to hide ambiguous models')
before={'file':bpy.data.filepath,'dirty':bpy.data.is_dirty,'mode':bpy.context.mode,
        'objects':[{'name':o.name,'hidden':o.hide_get(),'hide_viewport':o.hide_viewport,'hide_render':o.hide_render} for o in bpy.context.scene.objects]}
(directory/'visibility_before_clean_view.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
if bpy.context.mode!='OBJECT' and bpy.ops.object.mode_set.poll():bpy.ops.object.mode_set(mode='OBJECT')
roots=[o for o in bpy.context.scene.objects if getattr(o,'mmd_type','')=='ROOT']
for root in roots:
    for name in ('show_armature','show_rigid_bodies','show_joints','show_temporary_objects','show_names_of_rigid_bodies','show_names_of_joints'):
        if hasattr(root.mmd_root,name):setattr(root.mmd_root,name,False)
keep=set(model)
for obj in bpy.context.scene.objects:
    obj.select_set(False)
    obj.hide_set(obj not in keep)
    if obj in keep:obj.hide_viewport=False;obj.hide_render=False
    elif obj.type=='MESH':obj.hide_render=True
for obj in model:obj.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in model if not o.get('mmd_garment'))
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type!='VIEW_3D':continue
        space=area.spaces.active
        space.overlay.show_overlays=False;space.show_gizmo=False
        space.show_region_ui=False;space.show_region_toolbar=False
        space.shading.type='MATERIAL';space.shading.use_scene_lights=False;space.shading.use_scene_world=False
        space.shading.background_type='VIEWPORT';space.shading.background_color=(.055,.055,.065)
        space.region_3d.view_rotation=Vector((.24,-1,.025)).to_track_quat('Z','Y')
        space.region_3d.view_perspective='ORTHO'
        region=next((r for r in area.regions if r.type=='WINDOW'),None)
        if region:
            with bpy.context.temp_override(window=window,area=area,region=region):bpy.ops.view3d.view_selected(use_all_regions=False)
            space.region_3d.view_distance*=.86
for obj in model:obj.select_set(False)
bpy.context.view_layer.objects.active=None
bpy.context.view_layer.update()
unexpected=[o.name for o in bpy.context.scene.objects if o.visible_get() and o not in keep]
if unexpected:raise RuntimeError('Unexpected visible helper objects: '+repr(unexpected))
save=directory/'Daniya_WhiteBridal_Clean.blend'
if save.exists():save=directory/('Daniya_WhiteBridal_Clean_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(save))
report={'clean_file':str(save),'visible_meshes':[o.name for o in model],'visible_helpers':unexpected,
        'hidden_armatures':sum(o.type=='ARMATURE' and o.hide_get() for o in bpy.context.scene.objects),
        'hidden_rigid_bodies':sum(getattr(o,'mmd_type','')=='RIGID_BODY' and o.hide_get() for o in bpy.context.scene.objects),
        'all_object_count':len(bpy.context.scene.objects),'geometry_modified':False,'objects_deleted':0}
(directory/'clean_view_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('CLEAN_VIEW_READY',json.dumps(report,ensure_ascii=False))
