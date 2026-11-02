"""Load the shipped ZIP, including the generic route API, in a clean process."""
import sys,json,zipfile,importlib
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1]
receipt=json.loads((ROOT/'dist/animation_contact_package.json').read_text('utf8'))
expected=tuple(receipt['plugin_version']);version=''.join(map(str,expected));out=ROOT/('outputs/contact_package_'+version);out.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(receipt['plugin']) as z:z.extractall(out)
sys.path.insert(0,str(out))
module=importlib.import_module('animation_contact_tools')
assert module.bl_info['version']==expected
objects=set(bpy.data.objects)
module.register();module.unregister()
assert set(bpy.data.objects)==objects
for name in ['two_bone_contact_path','arm_detour_planner','hair_position_cache','root_envelope_feedback','skin_collision_cage','anatomical_colliders','surface_contact_projection','closed_collider_field','exact_skin_collider','hair_bundle_profile','arm_route_bake','attachment_contact','attachment_feedback']:
    importlib.import_module('animation_contact_tools.'+name)
from animation_contact_tools.arm_detour_planner import select_arm_route
n={'offset':[0.,0.,0.],'swivel':0.,'cost':0.}
r=select_arm_route([[n],[n]],[1,2],max_correction_speed=0.)
assert r['min_possible_peak_correction_step_m_per_frame']==0
result={'status':'PACKAGED_'+version+'_REGISTER_AND_ROUTE_IMPORT_PASS','scene_objects_preserved':True,'character_assets_required':False}
(out/'report.json').write_text(json.dumps(result),encoding='utf8')
print('CONTACT_PACKAGE_LOAD',json.dumps(result),flush=True)
