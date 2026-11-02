"""Package the best completed 450-frame upstream bake for honest visual review.

This reuses existing physical animation and body/wrist corrections. No new
solver, fallback motion, per-frame correction or hidden collision filtering.
"""
import argparse,json,sys,shutil,hashlib,time
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(a.candidate);out=Path(a.out)
out.mkdir(parents=True,exist_ok=True);assert not (out/'setup.json').exists(),'Use a fresh review directory'
config=json.loads((src/'configuration.json').read_text('utf8'));bake=json.loads((src/'bake_report.json').read_text('utf8'))
assert bake['frames']==[1,450] and bake['status']=='UPSTREAM_PLUGIN_BAKED_NOT_VISUALLY_ACCEPTED'
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=bake['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;s.frame_start=1;s.frame_end=450;s.render.fps=30;s.render.fps_base=1.
s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100;s.use_preview_range=False
s.render.use_sequencer=False;s.render.image_settings.file_format='PNG';s.render.use_file_extension=True
assert s.camera and not s.camera.animation_data and not s.camera.constraints,'Fixed original camera required'
if s.rigidbody_world:s.rigidbody_world.enabled=False
actor=bpy.data.objects['东雪莲x达妮娅_素体'];arm=actor.find_armature();assert len(actor.data.vertices)==68272
assert arm.animation_data and arm.animation_data.action,'Completed native bone bake required'
assert 'JigglePhysics' in arm.animation_data.action.name
cache=out/'cache';cache.mkdir(exist_ok=True);retained=[]
for obj in bpy.data.objects:
    for md in obj.modifiers:
        if md.type=='MESH_CACHE':
            original=Path(bpy.path.abspath(md.filepath));assert original.exists(),str(original)
            target=cache/original.name
            if not target.exists():shutil.copy2(original,target)
            assert target.stat().st_size==original.stat().st_size
            md.filepath=str(target);retained.append(dict(object=obj.name,path=str(target),bytes=target.stat().st_size))
for image in bpy.data.images:
    if image.filepath and image.source in {'FILE','MOVIE','SEQUENCE','TILED'}:
        image.filepath=bpy.path.abspath(image.filepath)
s['ReviewOnly']=True;s['ReviewPhysicsSource']=bake['blend'];s['ReviewAllHairCollisionSolved']=False
s['ReviewUsesCompletedPhysicalBake']=True;s['ReviewNoProceduralFallbackMotion']=True;s['ShutdownForbidden']=True
source_audit=json.loads((src/'audit450/surface_audit.json').read_text('utf8'));rows=source_audit['rows']
assert len(rows)==450 and {r['frame'] for r in rows}==set(range(1,451))
checks=[];camera=np.array(s.camera.matrix_world)
for frame in [1,234,310,331,380,450]:
    s.frame_set(frame);bpy.context.view_layer.update();x=coords(actor)
    assert np.isfinite(x).all() and np.max(np.abs(x))<100
    assert np.max(np.abs(np.array(s.camera.matrix_world)-camera))<1e-9
    checks.append(dict(frame=frame,actor_bbox=[x.min(0).tolist(),x.max(0).tolist()]))
s.frame_set(1);bpy.context.view_layer.update()
path=out/'完整角色_现有最佳流程_15秒预览.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
for name in ['configuration.json','bake_report.json']:
    shutil.copy2(src/name,out/('source_'+name))
shutil.copy2(src/'audit450/surface_audit.json',out/'source_geometry_audit.json')
report=dict(status='COMPLETED_EXISTING_PHYSICS_PACKAGED_FOR_VISUAL_REVIEW',blend=str(path),
    source_blend=bake['blend'],source_sha256=hashlib.sha256(Path(bake['blend']).read_bytes()).hexdigest(),
    source_candidate=str(src),plugin=config['plugin'],frames=[1,450],fps=30,resolution=[1920,1080],
    all_character_parts_preserved=True,original_materials_preserved=True,fixed_original_camera=True,
    retained_body_wrist_caches=retained,physics_bake_in_native_action=arm.animation_data.action.name,
    source_known_skin_crossing_frames=sum(r['crossings']>0 for r in rows),
    source_maximum_crossing_pairs=max(r['crossings'] for r in rows),
    source_maximum_edge_ratio=max(r['edge_ratio_max'] for r in rows),
    source_frame_331_skin_crossings=next(r['crossings'] for r in rows if r['frame']==331),
    all_hair_collision_solved=False,new_physics_computed=False,latest_bone_prototype_used=False,
    selection_reason='Completed full-range upstream bake with prior 450-frame review; latest bone28 is not yet a physical animation. Selected for current visual preview, not claimed globally optimal.',
    no_fallback_or_motion_filter=True,source_checks=checks,shutdown_forbidden=True)
(out/'setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['source_checks','plugin','retained_body_wrist_caches']},ensure_ascii=False),flush=True)
