import sys,argparse,json,shutil,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'addon'),str(ROOT/'scripts')]
from mmd_outfit.service import engine
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.tights import rebuild,material
from mmd_outfit.sleeve_rest import apply
from mmd_outfit.surface_clearance import relax_outside,shorten_cap
from mmd_outfit.skin_collision import collider,install
from mmd_outfit.nylon_shell import install as shell
from mmd_outfit.forearm_clearance import install as forearm_guard
from mmd_outfit.arm_weight_transfer import apply as arm_weights
from mmd_outfit.minimum_skin_gap import install as minimum_gap
from mmd_outfit.sleeve_lining import install as lining
from inspect_sleeves_stockings import parts

def digest(obj):
    h=hashlib.sha256()
    a=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',a);h.update(a.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',a);h.update(a.tobytes())
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    ie,garment,render=engine('import_export'),engine('garment'),engine('extraction');ie.ensure_mmd_tools()
    source=ROOT/'outputs/keqing_head/proportions_v2';bpy.ops.wm.open_mainfile(filepath=str(source/'work.blend'),load_ui=False,use_scripts=False)
    body=bpy.data.objects['达妮娅_mesh'];cloth=bpy.data.objects['Cloth'];arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    protect={o.name:digest(o) for o in ie.model_meshes() if o!=cloth}
    # Provenance recorded by the head transplant maps the exact checked feet.
    # The foot patch's ordering was recorded BEFORE fitting changed its shape.
    # Re-selecting by height on the fitted body yields a different set of IDs.
    foot_source=read_json(ROOT/'outputs/white_bridal_shoes/checked/contact_correction.json')['source']
    with bpy.data.libraries.load(foot_source,link=False) as (src,dst):dst.objects=['达妮娅_mesh']
    oldbody=dst.objects[0]
    foot_faces=[f for f in oldbody.data.polygons if oldbody.data.materials[f.material_index].mmd_material.name_j in {'Body','Nails'} and min(oldbody.data.vertices[i].co.z for i in f.vertices)<.1953568]
    oldids=sorted({i for f in foot_faces for i in f.vertices});assert len(oldids)==4968
    provenance=read_json(source/'neck_vertex_provenance.json')['body'];newids={v[0][0]:i for i,v in enumerate(provenance) if len(v)==1 and abs(v[0][1]-1)<1e-7}
    foot={newids[i]:cloth.data.vertices[len(cloth.data.vertices)-len(oldids)+k].co.copy() for k,i in enumerate(oldids)}
    foot_records={}
    for k,i in enumerate(oldids):
        ci=len(cloth.data.vertices)-len(oldids)+k
        foot_records[newids[i]]={'co':cloth.data.vertices[ci].co.copy(),'weights':[(cloth.vertex_groups[g.group].name,g.weight) for g in cloth.data.vertices[ci].groups],'keys':{key.name:key.data[ci].co.copy() for key in cloth.data.shape_keys.key_blocks}}
    bpy.data.objects.remove(oldbody,do_unlink=True)
    sleeve=apply(cloth,arm,read_json(ROOT/'outputs/stockings_sleeves/settle/settled.json'),parts(cloth,['新規','服+jinshu']))
    sleeve_parts=parts(cloth,['新規','服+jinshu']);sleeve['cap_tailoring']=shorten_cap(cloth,arm,sleeve_parts)
    sleeve['clearance']=relax_outside(cloth,body,{i for p in sleeve_parts for i in p['vertices']},margin=.003,iterations=28)
    sleeve['target_arm_weights']=arm_weights(cloth,body,arm,sleeve_parts)
    tex=out/'textures';tex.mkdir(exist_ok=True)
    mask_source=ROOT/'outputs/stockings_sleeves/reference/stocking_gold.png';shutil.copyfile(mask_source,tex/mask_source.name);gold=bpy.data.images.load(str(tex/mask_source.name),check_existing=False);gold.colorspace_settings.name='Non-Color'
    mat=material(gold);stock,report=rebuild(body,cloth,garment._copy_mesh_subset,foot_overrides=foot,foot_records=foot_records,material=mat)
    protected_feet=[(k,b[0][0]) for k,b in enumerate(report['target_vertices']) if len(b)==1 and b[0][0] in foot]
    assert len(protected_feet)==4968,'Lost fitted foot vertex provenance'
    assert max((stock.data.vertices[k].co-foot[i]).length for k,i in protected_feet)<1e-7
    report['hip_clearance']=relax_outside(stock,body,{v.index for v in stock.data.vertices if .83<v.co.z<1.03},margin=.0025,iterations=32)
    proxy=collider(body)
    report['direct_body_follow']=shell(stock,body,report['target_vertices'],foot)
    # The stocking removal changes garment numbering; never reuse pre-cut IDs.
    sleeve_parts=parts(cloth,['新規','服+jinshu'])
    sleeve['posed_skin_correction']=install(cloth,proxy,{i for p in sleeve_parts for i in p['vertices']},group_name='SleeveRegion',offset=.0035,subdivision=2)
    sleeve['forearm_clearance']=forearm_guard(cloth,body,arm)
    sleeve['minimum_skin_gap']=minimum_gap(cloth,proxy,'OutfitAudit_SleeveRegion')
    _,sleeve['fitted_lining']=lining(cloth,body,arm,skin=proxy)
    write_json(out/'stocking_provenance.json',{'target_vertices':report.pop('target_vertices')})
    protected={name:digest(bpy.data.objects[name])==hash_ for name,hash_ in protect.items()};assert all(protected.values()),'Unexpected body/head/shoe change'
    model=ie.model_meshes();scene=bpy.context.scene;scene.frame_set(1)
    for o in scene.objects:o.select_set(False);o.hide_set(o not in model);o.hide_render=o.type=='MESH' and o not in model
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                s=area.spaces.active;s.overlay.show_overlays=False;s.show_gizmo=False;s.shading.type='MATERIAL';s.region_3d.view_location=Vector((0,.02,.89));s.region_3d.view_distance=2.;s.region_3d.view_rotation=Vector((.15,-1,.03)).to_track_quat('Z','Y');s.region_3d.view_perspective='ORTHO'
    # Material data and mesh rig are portable; save before adding review lights.
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'work.blend'),compress=True);shutil.copyfile(out/'work.blend',out/'Keqing_Stockings_Sleeves.blend')
    evaluated=stock.evaluated_get(bpy.context.evaluated_depsgraph_get());report['live_mesh']={'vertices':len(evaluated.data.vertices),'faces':len(evaluated.data.polygons)}
    write_json(out/'repair_report.json',{'source':str(source/'work.blend'),'stockings':report,'sleeves':sleeve,'protected_body_head_shoes':protected})
    render._setup_render(scene,1000,1200);render._setup_lights(scene)
    data=bpy.data.cameras.new('RepairReview');data.type='ORTHO';camera=bpy.data.objects.new('RepairReview',data);scene.collection.objects.link(camera);scene.camera=camera
    for name,d,center,scale in [('front',(0,-1,.02),(0,.02,.83),1.75),('back',(0,1,.02),(0,.02,.83),1.75),('legs_front',(0,-1,.02),(0,.02,.55),1.12),('legs_back',(0,1,.02),(0,.02,.55),1.12),('sleeve_oblique',(1,-.7,.25),(.235,.02,1.20),.44)]:
        target=Vector(center);data.ortho_scale=scale;camera.location=target+Vector(d).normalized()*3;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    # Back hip fit, garment layers temporarily hidden for diagnosis only.
    for o in model:o.hide_render=o not in (body,stock)
    target=Vector((0,.03,.95));data.ortho_scale=.44;camera.location=target+Vector((0,3,.02));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/'hips_fit_back.png');bpy.ops.render.render(write_still=True)
    print('TIGHTS_SLEEVES_REBUILT',json.dumps({'stockings':report,'sleeves':sleeve,'protected':all(protected.values())},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
