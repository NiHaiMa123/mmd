"""Continuous sleeve-only MMD Tools physics review, with posed skin guards.

Other secondary dynamics are omitted. This is not native MMD acceptance.
"""
import sys,argparse,json
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import write_json
from review_tights_sleeves import contacts,evaluate
from inspect_sleeves_stockings import parts

def main():
    p=argparse.ArgumentParser();p.add_argument('--fit',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);fit=Path(a.fit).resolve();out=fit/'physics_review';out.mkdir(exist_ok=True)
    ie,render=engine('import_export'),engine('extraction');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(fit/'work.blend'),load_ui=False,use_scripts=False)
    body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings'];cloth=bpy.data.objects['Cloth'];arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');scene=bpy.context.scene
    model=ie.model_meshes(list(scene.objects));visibility={o:(o.hide_viewport,o.hide_render) for o in model}
    arm.hide_set(False);arm.select_set(True);bpy.context.view_layer.objects.active=arm;bpy.ops.mmd_tools.import_vmd(filepath=str(ROOT/'outputs/keqing_head/proportions_v2/mmd/grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
    rigids={o for o in bpy.data.objects if getattr(o,'mmd_type','')=='RIGID_BODY'};kept={o for o in rigids if str(o.mmd_rigid.type)=='0' or o.mmd_rigid.bone.startswith('袖_')}
    for o in [o for o in bpy.data.objects if getattr(o,'mmd_type','')=='JOINT' and (o.rigid_body_constraint.object1 not in kept or o.rigid_body_constraint.object2 not in kept)]+list(rigids-kept):bpy.data.objects.remove(o,do_unlink=True)
    for o in model:o.hide_viewport=True;o.hide_render=True
    setup=engine('physics_sim').setup_native(scene,arm,1,256)
    names={g.index:g.name for g in body.vertex_groups};arm_ids={v.index for v in body.data.vertices if sum(g.weight for g in v.groups if names[g.group].startswith(('腕','ひじ','肩')) and not names[g.group].startswith('mmd_'))>.5};sleeve_ids={i for p in parts(cloth,['新規','服+jinshu']) for i in p['vertices']}
    render._setup_render(scene,1000,1100);render._setup_lights(scene);data=bpy.data.cameras.new('SleevePhysicsReview');data.type='ORTHO';cam=bpy.data.objects.new('SleevePhysicsReview',data);scene.collection.objects.link(cam);scene.camera=cam;results={}
    for frame in range(1,257):
        scene.frame_set(frame);bpy.context.view_layer.update()
        if frame%50==0:print('SLEEVE_PHYSICS_FRAME',frame,flush=True)
        if frame not in (1,121,256):continue
        for o,(hv,hr) in visibility.items():o.hide_viewport=hv;o.hide_render=hr
        bpy.context.view_layer.update();results[str(frame)]=contacts(body,stock,cloth,arm_ids,sleeve_ids)
        center=sum((arm.matrix_world@arm.pose.bones['腕.'+s].head for s in ('L','R')),Vector())*.5+Vector((0,0,-.10));data.ortho_scale=1.05
        for name,direction in [('front',(0,-1,.04)),('oblique',(1,-1,.10)),('back',(0,1,.04))]:
            cam.location=center+Vector(direction).normalized()*3;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{frame}_{name}.png');bpy.ops.render.render(write_still=True)
        for o in model:o.hide_viewport=True;o.hide_render=True
    write_json(out/'report.json',{'setup':setup,'scope':'sleeve dynamics plus kinematic body colliders; other secondary dynamics omitted; Blender only','frames':results})
    print('SLEEVE_PHYSICS_CONTACTS',json.dumps({f:r['sleeves_crossing_pairs'] for f,r in results.items()}),flush=True)
    bpy.data.batch_remove(ids=[o for o in bpy.data.objects if o.rigid_body_constraint]);bpy.ops.rigidbody.world_remove()

if __name__=='__main__':main()
