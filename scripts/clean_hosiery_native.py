"""Save the plate-free neutral model and compare the clothed crotch region."""
import sys,json,hashlib
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.hosiery_cleanup import clean
ie=engine('import_export');ie.ensure_mmd_tools();source=ROOT/'outputs/stockings_sleeves/review_ready/work.blend';bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
out=ROOT/'outputs/cynical_cloth15/clean_model';out.mkdir(parents=True,exist_ok=True);body=bpy.data.objects['达妮娅_mesh'];stock=bpy.data.objects['Stockings']
def digest(obj):
    h=hashlib.sha256();a=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',a);h.update(a.tobytes())
    if obj.data.shape_keys:
        for k in obj.data.shape_keys.key_blocks:k.data.foreach_get('co',a);h.update(a.tobytes())
    return h.hexdigest()
before={o.name:digest(o) for o in ie.model_meshes()};result=clean(body,stock);assert all(digest(bpy.data.objects[n])==h for n,h in before.items())
result['all_model_vertex_and_morph_coordinates_unchanged']=True
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Keqing_PlateRemoved.blend'),compress=True)
(out/'cleanup.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
scene=bpy.context.scene;render=engine('extraction');render._setup_render(scene,750,750);render._setup_lights(scene)
data=bpy.data.cameras.new('CleanupDiagnostic');data.type='ORTHO';data.ortho_scale=.20;cam=bpy.data.objects.new('CleanupDiagnostic',data);scene.collection.objects.link(cam);scene.camera=cam
target=Vector((0,.025,.90));cam.location=target+Vector((.12,-1,-.45)).normalized()*2;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(out/'crotch_after.png');bpy.ops.render.render(write_still=True)
print('HOSIERY_PLATE_REMOVED',result['disconnected_gusset_branches'],result['internal_faces_excluded_from_nylon'],flush=True)
