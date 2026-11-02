"""Separate stale authored normals from folded chest geometry, read-only."""
import sys,json
from pathlib import Path
from collections import Counter
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
ie=engine('import_export');ie.ensure_mmd_tools();out=ROOT/'outputs/chest_repair/probe';out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(ROOT/'outputs/cynical_cloth15/structured_v2/Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False)
scene=bpy.context.scene;scene.frame_set(1);cloth=bpy.data.objects['Cloth'];body=bpy.data.objects['达妮娅_mesh'];faces=json.loads((ROOT/'outputs/cynical_cloth15/inspection.json').read_text(encoding='utf-8'))['Cloth']['all_islands'][2]['faces'];ids={i for fi in faces for i in cloth.data.polygons[fi].vertices};report={'has_custom_normals':cloth.data.has_custom_normals,'smooth_chest_faces':sum(cloth.data.polygons[i].use_smooth for i in faces),'base_front_facing_backwards':sum(cloth.data.polygons[i].normal.y>.2 for i in faces),'chest_bounds':[[min(cloth.data.vertices[i].co[k] for i in ids),max(cloth.data.vertices[i].co[k] for i in ids)] for k in range(3)]}
render=engine('extraction');render._setup_render(scene,1080,1080);scene.view_settings.view_transform='AgX';data=bpy.data.cameras.new('ChestProbe');data.type='ORTHO';data.ortho_scale=.34;cam=bpy.data.objects.new('ChestProbe',data);scene.collection.objects.link(cam);scene.camera=cam;center=Vector((0,-.055,1.235));cam.location=center+Vector((.1,-1,.1)).normalized()*2;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
cloth.data=cloth.data.copy();cloth.data.normals_split_custom_set([(0.,0.,0.)]*len(cloth.data.loops))
scene.render.filepath=str(out/'computed_normals.png');bpy.ops.render.render(write_still=True)
mat=bpy.data.materials.new('ChestProbeGray');mat.use_nodes=True;shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');shader.inputs['Base Color'].default_value=(.4,.4,.4,1);shader.inputs['Roughness'].default_value=.8;scene.view_layers[0].material_override=mat;scene.render.filepath=str(out/'computed_normals_gray.png');bpy.ops.render.render(write_still=True)
(out/'probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('CHEST_NORMAL_PROBE',json.dumps(report),flush=True)
