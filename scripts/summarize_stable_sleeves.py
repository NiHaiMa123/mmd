"""Verify the completed replacement clip and record actual sleeve evidence."""
import json,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'outputs/cynical_cloth15/sleeve_stable'
def read(name):return json.loads((out/name).read_text(encoding='utf-8'))
audit=read('sleeve_dense_audit.json');shape=read('sleeve_shape_repair.json');video=read('video_report.json');progress=read('render_progress.json');comparison=read('comparison_report.json');v=next(s for s in video['streams'] if s['codec_type']=='video')
assert len(audit['frames']['after'])==450 and audit['protected_meshes_and_morphs']==24
assert audit['skirt_target_max_difference_m']==0 and audit['projected_target_cache_max_error_m']==0 and audit['new_cache_random_seek_error_m']==0
for side in ('L','R'):
 interval=audit['summary']['after'][side];assert interval['interval_min_edge_ratio']>.7 and interval['interval_max_edge_ratio']<1.35
 assert min(row[side]['edge_ratio_min'] for row in audit['frames']['after'].values())>.68
 assert max(row[side]['edge_ratio_max'] for row in audit['frames']['after'].values())<1.4
assert (v['width'],v['height'],v['avg_frame_rate'],int(v['nb_frames']))==(1920,1080,'30/1',450)
assert abs(float(video['format']['duration'])-15)<.01 and video['native_render'] and any(s['codec_type']=='audio' for s in video['streams'])
assert progress['status']=='complete' and progress['rendered']==450
assert len(list((out/'sleeve_review').glob('*.png')))==27
cache=out/'StableSleeveShapes.pc2';magic,version,points,start,rate,count=struct.unpack('<12siiffi',cache.read_bytes()[:32]);assert magic==b'POINTCACHE2\0' and points==978 and count==496
package=ROOT/'dist/mmd_outfit_bridge-0.9.0-sleeve-stable-20261027.zip'
result={'status':'SLEEVE_CORRECTION_PREVIEW_READY','video':video['output'],'comparison':comparison['output'],'project':str(out/'Cynical_Cloth_15s.blend'),'resolution':[1920,1080],'fps':30,'frames':450,'seconds':15,'method':shape['method'],'physical_input':'Existing baked Blender CLOTH, followed by shape and temporal constraints; not a new pure solver bake','problem_interval_seconds':[12,14],'interval_metrics':audit['summary']['after'],'protected_meshes_and_morphs':24,'skirt_target_difference_m':0,'pose_cache_sha256':hashlib.sha256(cache.read_bytes()).hexdigest(),'package':str(package),'package_sha256':hashlib.sha256(package.read_bytes()).hexdigest(),'remaining':['Minor waistband layer intersection remains.','Full hair dynamics, full song and native PMX/MMD runtime remain unvalidated.'],'required_project_companions':['StableSleeveShapes.pc2','blendcache_Cynical_Cloth_15s/']}
(out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('SLEEVE_CORRECTION_READY',json.dumps({k:result[k] for k in ('status','resolution','fps','seconds','video','comparison')}),flush=True)
