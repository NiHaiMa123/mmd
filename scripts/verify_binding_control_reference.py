"""Read-only independent check that native bend fields use identical bounds."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--benchmark',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.benchmark)
engine('import_export').ensure_mmd_tools()
bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_绑定验证_非物理成片.blend'),use_scripts=False,load_ui=False)
s=bpy.context.scene;display=bpy.data.objects[s['HairDisplayObject']]
sd=next(m for m in display.modifiers if m.type=='SURFACE_DEFORM');target=sd.target
ref=bpy.data.objects['Benchmark_DirectReference_AllHair']
bend=next(m for m in target.modifiers if m.type=='SIMPLE_DEFORM')
assert bend.show_viewport and abs(bend.angle-np.deg2rad(5))<1e-6
saved=coords(target).copy();bend.show_viewport=False;bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get();ev=target.evaluated_get(deps)
me=bpy.data.meshes.new_from_object(ev,preserve_all_data_layers=True,depsgraph=deps)
clone=bpy.data.objects.new('ReferenceVerification_IdenticalCage',me);s.collection.objects.link(clone)
clone.matrix_world=target.matrix_world.copy();clone.hide_render=True
def local_bounds(obj):
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    try:
        ar=np.array([v.co[:] for v in mesh.vertices]);return np.stack([ar.min(0),ar.max(0)])
    finally:ev.to_mesh_clear()
target_bounds=local_bounds(target)
rb=next(m for m in ref.modifiers if m.type=='SIMPLE_DEFORM');rb.show_viewport=False;bpy.context.view_layer.update()
reference_bounds=local_bounds(ref);rb.show_viewport=True
check=clone.modifiers.new('IdenticalNativeBend','SIMPLE_DEFORM')
for name in ['deform_method','deform_axis','angle','limits','lock_x','lock_y','lock_z','origin']:
    if hasattr(bend,name):setattr(check,name,getattr(bend,name))
bend.show_viewport=True;bpy.context.view_layer.update()
actual=coords(target);identical=coords(clone)
report=dict(new_physics_frames=0,reference_bound_error_m=float(np.max(np.abs(target_bounds-reference_bounds))),
    identical_cage_bend_error_m=float(np.max(np.abs(actual-identical))),
    original_target_state_restored_error_m=float(np.max(np.abs(actual-saved))),
    target_bend_angle_degrees=float(np.rad2deg(bend.angle)),target_bend_axis=bend.deform_axis,
    actual_display_matches_saved_sample_error_m=None)
z=np.load(out/'bend_plus_5deg.npz')
report['actual_display_matches_saved_sample_error_m']=float(np.max(np.abs(coords(display)-z['actual'])))
report['reference_calibration_pass']=(report['reference_bound_error_m']<5e-6
    and report['identical_cage_bend_error_m']<5e-6 and report['actual_display_matches_saved_sample_error_m']<5e-6)
(out/'reference_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
assert report['reference_calibration_pass'],'Native reference calibration failed; do not infer binding causality'
