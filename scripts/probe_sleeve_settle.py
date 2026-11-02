import sys,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/work.blend'),load_ui=False,use_scripts=False)
arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');cloth=bpy.data.objects['Cloth'];out=ROOT/'outputs/stockings_sleeves/settle';out.mkdir(parents=True,exist_ok=True)
rigids={o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY'};kept={o for o in rigids if str(o.mmd_rigid.type)=='0' or o.mmd_rigid.bone.startswith(('袖_','袖環'))}
for o in [o for o in bpy.data.objects if getattr(o,'mmd_type','')=='JOINT' and (o.rigid_body_constraint.object1 not in kept or o.rigid_body_constraint.object2 not in kept)]+list(rigids-kept):bpy.data.objects.remove(o,do_unlink=True)
setup=engine('physics_sim').setup_native(bpy.context.scene,arm,1,100)
for f in range(1,101):
    bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
    if f%20==0:print('SETTLE',f,flush=True)
deps=bpy.context.evaluated_depsgraph_get();evaluated=cloth.evaluated_get(deps);mesh=evaluated.to_mesh()
data={'setup':setup,'vertices':[list(v.co) for v in mesh.vertices],'bones':{p.name:[list(r) for r in p.matrix] for p in arm.pose.bones if p.name.startswith(('袖_','袖環'))}}
(out/'settled.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');evaluated.to_mesh_clear()
scene=bpy.context.scene
for o in bpy.data.objects:o.hide_render=True
for o in ie.model_meshes():o.hide_render=False
render._setup_render(scene,900,1000);render._setup_lights(scene)
camdata=bpy.data.cameras.new('Settled');camdata.type='ORTHO';camdata.ortho_scale=.90;cam=bpy.data.objects.new('Settled',camdata);scene.collection.objects.link(cam);scene.camera=cam;center=Vector((0,.02,1.18))
for name,d in [('front',(0,-1,.02)),('back',(0,1,.02)),('side',(1,0,.03))]:
    cam.location=center+Vector(d).normalized()*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
print('SETTLE_DONE',flush=True)
