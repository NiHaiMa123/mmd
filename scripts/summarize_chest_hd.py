"""Publish evidence for the repaired chest and native 1080p review clip."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'outputs/cynical_cloth15/chest_hd'
def read(name):return json.loads((out/name).read_text(encoding='utf-8'))
repair=read('chest_repair.json');cache=read('cache_reload_report.json');geometry=read('chest_geometry_audit.json');video=read('video_report.json');inspection=read('chest_review/inspection.json');plan=read('render_plan.json');progress=read('render_progress.json');v=next(s for s in video['streams'] if s['codec_type']=='video')
assert repair['protected_original_meshes']==23 and repair['nonpanel_coordinates_unchanged']
assert repair['morph_delta_max_error_m']<5e-7
assert cache['cache_baked_on_reload'] and max(s['bounds_error_m'] for s in cache['frames'].values())<1e-5
assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_frames']))==(1920,1080,'30/1',450)
assert abs(float(video['format']['duration'])-15)<.01 and video['native_render']
assert progress['status']=='complete' and progress['rendered']==450
assert inspection['chest_in_cloth_simulation']==0 and len(inspection['views'])==25
assert all(Path(path).is_file() for path in inspection['views'])
assert all((out/'chest_review'/f'solid_{name}.png').exists() for name in ('front','left_45','right_45'))
package=ROOT/'dist/mmd_outfit_bridge-0.9.0-chest-hd-20261027.zip'
result={'status':'HD_PREVIEW_READY_WITH_REMAINING_LAYER_INTERSECTION','resolution':[1920,1080],'fps':30,'duration_s':15,'frames':450,'native_render':True,'background':'white wall','music':'supplied Shikako cover','physical_solver':'Blender CLOTH with shape-preserving blend on skirts/sleeve ends; skinned tailored chest','chest_repair':repair,'chest_geometry':geometry,'visual_review_images':28,'cache_reload_verified':True,'video':video['output'],'project':str(out/'Cynical_Cloth_15s.blend'),'package':str(package),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'remaining':['Inner waistband island 4 intersects outer corset locally in the final closeup; experimental skin-gap and weight changes were not applied.','Full song, full hair dynamics and native MMD/PMX runtime are not validated.']}
(out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('CHEST_HD_REVIEW_READY',json.dumps({k:result[k] for k in ('status','resolution','fps','duration_s','frames','video','project')}),flush=True)
