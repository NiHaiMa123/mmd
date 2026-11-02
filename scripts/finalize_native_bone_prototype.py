"""Package neutral native bone prototype without unused shared-cage runtime."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from animation_contact_tools.surface import coords
p=argparse.ArgumentParser();p.add_argument('--prototype',required=True);p.add_argument('--old-candidate',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.prototype);old=Path(a.old_candidate)
cfg=json.loads((old/'configuration.json').read_text('utf8'))
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(out/'完整角色_27分束原始蒙皮_未启用物理.blend'),use_scripts=False,load_ui=False)
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();hair=bpy.data.objects[s['HairDisplayObject']]
actor=bpy.data.objects['东雪莲x达妮娅_素体'];hair_before=coords(hair);body_before=coords(actor)
removed=[]
for ob in list(bpy.data.objects):
    legacy=(ob.name in ['HairProxy_全头共享几何体积',cfg['physics_binding_target']]
        or (ob!=hair and any(m.type=='SURFACE_DEFORM' for m in ob.modifiers)))
    if legacy:removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
for name in ['Cloth_放大空间头部附着','Cloth_模拟坐标尺度']:
    ob=bpy.data.objects.get(name)
    if ob and not ob.children:removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
collider=bpy.data.objects['Jiggle_身体碰撞_含头手臂腕部']
collider.matrix_world=Matrix.Scale(1/cfg['simulation_scale'],4)@collider.matrix_world
for md in list(collider.modifiers):
    if md.type=='COLLISION':collider.modifiers.remove(md)
bpy.context.view_layer.update()
exp=ROOT.parent/'work/headswap_xl_codex/fullhair_repro_20261030/input_body_aware'
expected=np.load(exp/'body.npy',mmap_mode='r')[0]
collider_error=float(np.max(np.abs(coords(collider)-expected)))
hair_error=float(np.max(np.abs(coords(hair)-hair_before)));body_error=float(np.max(np.abs(coords(actor)-body_before)))
assert max(hair_error,body_error,collider_error)<5e-6
assert not any(md.type in {'SURFACE_DEFORM','CLOTH'} for ob in bpy.data.objects for md in ob.modifiers)
report=dict(status='NATIVE_BONE_PROTOTYPE_PACKAGED_NO_PHYSICS',removed_unused_objects=removed,
    displayed_hair_error_m=hair_error,body_error_m=body_error,collision_body_replay_error_m=collider_error,
    active_hair_deformation=[m.type for m in hair.modifiers],guide_objects=sum(o.name.startswith('Guide_') for o in bpy.data.objects),
    new_physics_frames=0,shutdown_forbidden=True)
path=out/'完整角色_27分束骨链_待接原生物理.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
report['blend']=str(path);(out/'packaging.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
print(json.dumps(report,ensure_ascii=False),flush=True)
