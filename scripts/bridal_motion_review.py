"""Ground and inspect the exported bridal-shoe PMX on the existing VMD."""
import argparse,sys
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.jobs import read_json,write_json
from mmd_outfit.service import engine
from mmd_outfit.motion_grounding import ground
from mmd_outfit.preserved_shoe import vertex_morph_report
p=argparse.ArgumentParser();p.add_argument('--fit',required=True);p.add_argument('--reuse-grounded',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.fit).resolve();model=out/'mmd';review=out/'motion_review';review.mkdir(exist_ok=True)
report=read_json(out/'fit_report.json');base=Path(report['input_job']);base_result=read_json(base/'result.json');original=read_json(base_result['grounding_report'])['source']
ie,render=[engine(n) for n in ('import_export','extraction')]
ie.clear_scene();objects=ie.import_pmx(str(model/'model.pmx'));mesh=ie.model_meshes(objects)[0];arm=next(o for o in objects if o.type=='ARMATURE')
ids=sorted({i for f in mesh.data.polygons if mesh.data.materials[f.material_index].name=='WhiteBridal' for i in f.vertices})
if not ids:raise ValueError('Exported shoe material is missing')
reference=[list(mesh.data.vertices[i].co) for i in ids]
if a.reuse_grounded:
    grounding=read_json(out/'grounding_report.json')
    bpy.context.scene.frame_set(1);bpy.context.view_layer.objects.active=arm;arm.select_set(True)
    bpy.ops.mmd_tools.import_vmd(filepath=str(model/'grounded.vmd'),scale=.08,rename_bones=True,margin=0,log_level='ERROR')
else:
    grounding=ground(mesh,arm,original,model/'grounded.vmd',['WhiteBridal'],engine,reference_points=reference,max_lift=.06,notify=lambda x:print(x,flush=True))
write_json(out/'grounding_report.json',grounding)
write_json(out/'shoe_reference.json',{'materials':['WhiteBridal'],'reference_positions':reference})
# Reimporting the generated VMD and the all-frame height verification happen
# inside generate(). Here inspect evaluated foot/stocking/shoe geometry as well.
render._setup_render(bpy.context.scene,1000,850);render._setup_lights(bpy.context.scene)
data=bpy.data.cameras.new('BridalMotionCamera');data.type='ORTHO';data.ortho_scale=.45
camera=bpy.data.objects.new('BridalMotionCamera',data);bpy.context.scene.collection.objects.link(camera);bpy.context.scene.camera=camera
ratios=[];shots=[];shoe_id_set=set(ids)
edges=[(e.vertices[0],e.vertices[1],(mesh.data.vertices[e.vertices[0]].co-mesh.data.vertices[e.vertices[1]].co).length)
       for e in mesh.data.edges if e.vertices[0] in shoe_id_set and e.vertices[1] in shoe_id_set]
for frame in (1,121,256):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();evaluated=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());me=evaluated.to_mesh()
    ratio=max((abs((me.vertices[i].co-me.vertices[j].co).length/length-1) for i,j,length in edges if length>.005),default=0.)
    absolute=max((abs((me.vertices[i].co-me.vertices[j].co).length-length) for i,j,length in edges),default=0.)
    points=[me.vertices[i].co.copy() for i in ids]
    minimum=min(p.z for p in points);evaluated.to_mesh_clear()
    shots.append({'frame':frame,'min_shoe_height_m':minimum,'max_relative_edge_error_over_5mm':ratio,'max_absolute_edge_error_m':absolute})
    lo=Vector([min(p[j] for p in points) for j in range(3)]);hi=Vector([max(p[j] for p in points) for j in range(3)])
    center=(lo+hi)*.5;data.ortho_scale=max(.40,max(hi-lo)*1.3)
    bone=arm.pose.bones['足首D.L'];orientation=(bone.matrix@bone.bone.matrix_local.inverted()).to_3x3()
    for name,direction in [('oblique',(1,-1,.2)),('side',(1,0,.08))]:
        camera.location=center+(orientation@Vector(direction)).normalized()*3;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.scene.render.filepath=str(review/f'{frame}_{name}.png');bpy.ops.render.render(write_still=True)
morph=vertex_morph_report(mesh,ids)
result={'shoe_vertices':len(ids),'morphs':morph,'shots':shots,'grounding':{k:grounding[k] for k in ('frames','verified_frames','min_height_verified_m','max_lift_m')},
        'scope':'flat-floor grounding verified per frame; geometry/visual checks only at 1,121,256; no native MMD dynamics acceptance'}
write_json(out/'motion_review.json',result)
assert not morph['changed_keys'] and all(x['max_absolute_edge_error_m']<1e-5 and x['max_relative_edge_error_over_5mm']<.001 for x in shots)
print('BRIDAL_MOTION_REVIEW',result,flush=True)
