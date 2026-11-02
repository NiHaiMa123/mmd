"""Restore only the tailored chest panel; preserve cached skirt/sleeve physics."""
import sys,json,shutil,argparse,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.chest_panel import restore
p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/chest_repair/fitted_v1');p.add_argument('--margin',type=float,default=.003);p.add_argument('--torso',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);out=(ROOT/a.out).resolve();out.mkdir(parents=True,exist_ok=True);source=ROOT/'outputs/cynical_cloth15/structured_v2';ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str(source/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(1);cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];arm=bpy.data.objects['达妮娅_arm'];template=json.loads((ROOT/('outputs/chest_repair/source/torso_coordinates.json' if a.torso else 'outputs/chest_repair/source/source_coordinates.json')).read_text(encoding='utf-8'));faces=template['faces'] if a.torso else json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'][2]['faces'];template['blend_boundaries']=a.torso;ids=sorted({i for fi in faces for i in cloth.data.polygons[fi].vertices});mask=np.ones(len(cloth.data.vertices),dtype=bool);mask[ids]=False
def digest(obj):
    h=hashlib.sha256();data=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',data);h.update(data.tobytes())
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',data);h.update(data.tobytes())
    return h.hexdigest()
protected={o.name:digest(o) for o in ie.model_meshes() if o!=cloth};before=np.array([v.co[:] for v in cloth.data.vertices]);basis=np.array([v.co[:] for v in cloth.data.shape_keys.key_blocks[0].data]);deltas={k.name:np.array([k.data[i].co[:] for i in ids])-basis[ids] for k in cloth.data.shape_keys.key_blocks};nonpanel=hashlib.sha256()
for key in cloth.data.shape_keys.key_blocks:
    data=np.array([v.co[:] for v in key.data],dtype=np.float32);nonpanel.update(data[mask].tobytes())
template['restore_shading_normals']=a.torso;template['torso_weight_guard']=a.torso;report=restore(cloth,body,arm,faces,template,margin=a.margin);check=hashlib.sha256();morph_error=0.;newbasis=np.array([v.co[:] for v in cloth.data.shape_keys.key_blocks[0].data])
for key in cloth.data.shape_keys.key_blocks:
    data=np.array([v.co[:] for v in key.data],dtype=np.float32);check.update(data[mask].tobytes());morph_error=max(morph_error,float(np.abs((data[ids]-newbasis[ids])-deltas[key.name]).max()))
assert nonpanel.hexdigest()==check.hexdigest(),'Non-panel shape coordinates changed'
assert morph_error<5e-7,morph_error
assert all(digest(bpy.data.objects[name])==value for name,value in protected.items()),'Protected original meshes changed'
report.update({'protected_original_meshes':len(protected),'body_head_shoes_unchanged':True,'nonpanel_coordinates_unchanged':True,'morph_delta_max_error_m':morph_error,'source':str(source),'render_resolution':[1920,1080]})
(out/'torso_template.json').write_text(json.dumps(template,ensure_ascii=False),encoding='utf-8')
for name in ('blendcache_Cynical_Cloth_15s',):shutil.copytree(source/name,out/name,dirs_exist_ok=True)
for name in ('setup.json','simulation_report.json','cloth_setup.json','CREDITS.txt'):shutil.copyfile(source/name,out/name)
scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100;scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True)
(out/'chest_repair.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('CHEST_PANEL_REPAIRED',json.dumps(report),flush=True)
# Focused inspection stills; the saved project keeps the supplied camera.
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('ChestRepairInspect');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('ChestRepairInspect',data);scene.collection.objects.link(cam);scene.camera=cam;scene.frame_set(1);target=arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.055,.015))
for name,d in [('front',(0,-1,0)),('left_45',(-1,-1,0)),('right_45',(1,-1,0))]:
    cam.location=target+Vector(d).normalized()*2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/('chest_'+name+'.png'));bpy.ops.render.render(write_still=True)
