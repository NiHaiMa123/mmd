"""Large chest closeups, solid-shading control, and actual-region inventory."""
import argparse,json,sys
from pathlib import Path
from collections import Counter
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--fit',default='outputs/cynical_cloth15/structured_v2');p.add_argument('--out',default='outputs/chest_repair/before');a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []);out=(ROOT/a.out).resolve();out.mkdir(parents=True,exist_ok=True)
ie=engine('import_export');ie.ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=str((ROOT/a.fit/'Cynical_Cloth_15s.blend').resolve()),load_ui=False,use_scripts=False)
scene=bpy.context.scene;cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];faces=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'][2]['faces'];ids=sorted({i for fi in faces for i in cloth.data.polygons[fi].vertices});names={g.index:g.name for g in cloth.vertex_groups};selection=cloth.data.attributes.get('OutfitStructuredClothSelection');report={'chest_vertices':len(ids),'chest_faces':len(faces),'chest_in_cloth_simulation':sum(selection.data[i].value for i in ids) if selection else None,'bones':dict(Counter(names[g.group] for i in ids for g in cloth.data.vertices[i].groups if g.weight>.1 and not names[g.group].startswith('mmd_'))),'modifiers':[(m.name,m.type) for m in cloth.modifiers],'views':[]}
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX'
data=bpy.data.cameras.new('ChestInspection');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('ChestInspection',data);scene.collection.objects.link(cam);scene.camera=cam
def center():
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');return arm.matrix_world@((arm.pose.bones['上半身2'].head+arm.pose.bones['上半身2'].tail)*.5)+Vector((0,-.055,.015))
views=[('front',(0,-1,0)),('left_45',(-1,-1,0)),('right_45',(1,-1,0)),('left_side',(-1,0,0)),('right_side',(1,0,0)),('above',(0,-1,.6)),('below',(0,-1,-.6))]
for label,frame in [('neutral',1),('opening',47),('mid_150',196),('mid_240',286),('mid_270',316),('arms_up',376),('end_450',496)]:
    scene.frame_set(frame);bpy.context.view_layer.update();target=center()
    for name,direction in views if label=='neutral' else views[:3]:
        cam.location=target+Vector(direction).normalized()*2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'{label}_{name}.png');bpy.ops.render.render(write_still=True);report['views'].append(scene.render.filepath)
# Same surface with a plain material separates actual geometry from the
# painted highlights and author-provided shading normals.
mat=bpy.data.materials.new('ChestDiagnosticGray');mat.use_nodes=True;shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');shader.inputs['Base Color'].default_value=(.4,.4,.4,1);shader.inputs['Roughness'].default_value=.8
scene.view_layers[0].material_override=mat;scene.frame_set(1);target=center()
for name,direction in views[:3]:
    cam.location=target+Vector(direction).normalized()*2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/f'solid_{name}.png');bpy.ops.render.render(write_still=True)
(out/'inspection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('CHEST_MULTIVIEW_COMPLETE',report['chest_in_cloth_simulation'],report['bones'],flush=True)
