"""Install a sleeve-only solver onto the chest repair; preserve original assets."""
import sys,json,shutil,hashlib
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
from mmd_outfit.stable_sleeve_cloth import _install_experimental_solver as install
engine('import_export').ensure_mmd_tools();source=ROOT/'outputs/cynical_cloth15/chest_hd';out=ROOT/'outputs/cynical_cloth15/sleeve_fixed';out.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(source/'Cynical_Cloth_15s.blend'),load_ui=False,use_scripts=False);scene=bpy.context.scene;scene.frame_set(1)
def digest(obj):
 h=hashlib.sha256();data=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',data);h.update(data.tobytes())
 if obj.data.shape_keys:
  for key in obj.data.shape_keys.key_blocks:key.data.foreach_get('co',data);h.update(data.tobytes())
 return h.hexdigest()
protected={o.name:digest(o) for o in engine('import_export').model_meshes()};proxy,sim,report=install(bpy.data.objects['ClothSimulationSurface'],bpy.data.objects['ClothKinematicReference'],bpy.data.objects['ClothShapePreservingTarget'],bpy.data.objects['ClothUnskinnedVisualCarrier'],bpy.data.objects['达妮娅_arm'],bpy.data.objects['Outfit_SkinCollider'])
assert all(digest(bpy.data.objects[name])==value for name,value in protected.items()),'Original mesh coordinates changed'
report.update({'protected_original_meshes':len(protected),'all_original_coordinates_and_morphs_unchanged':True,'original_mesh_hashes':protected,'source':str(source)})
shutil.copytree(source/'blendcache_Cynical_Cloth_15s',out/'blendcache_Cynical_Cloth_15s',dirs_exist_ok=True)
for name in ('setup.json','simulation_report.json','cloth_setup.json','CREDITS.txt','chest_repair.json','torso_template.json','chest_geometry_audit.json'):shutil.copyfile(source/name,out/name)
scene['stable_sleeve_cloth_version']=1;scene.frame_set(47);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Cynical_Cloth_15s.blend'),compress=True);(out/'sleeve_repair_setup.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('STABLE_SLEEVES_PREPARED',json.dumps({k:v for k,v in report.items() if k!='original_mesh_hashes'}),flush=True)
