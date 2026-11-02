"""Package the completed bone bake; preserve simulation/source project."""
import bpy,sys,json,argparse,struct,hashlib,numpy as np
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.run)
r=json.loads((out/'result.json').read_text('utf8'));assert r['frames']==[1,450] and not r['stop']
engine('import_export').ensure_mmd_tools();bpy.ops.wm.open_mainfile(filepath=r['blend'],load_ui=False,use_scripts=False)
s=bpy.context.scene;actor=bpy.data.objects['东雪莲x达妮娅_素体'];assert len(actor.data.vertices)==68272;assert len(actor.data.shape_keys.key_blocks)==232
assert s.camera and not s.camera.animation_data and not s.camera.constraints
cache=[]
for ob in bpy.data.objects:
 for md in ob.modifiers:
  if md.type=='MESH_CACHE':
   path=Path(bpy.path.abspath(md.filepath));assert path.is_file()
   with path.open('rb') as stream:magic,version,points,first,step,samples=struct.unpack('<12siiffi',stream.read(32))
   assert magic==b'POINTCACHE2\0' and path.stat().st_size==32+points*samples*12
   cache.append(dict(object=ob.name,path=str(path),points=points,samples=samples,first=first,step=step,play_mode=md.play_mode,time_mode=md.time_mode,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
motion=np.load(out/'native_rod_physics.npz');assert motion['coordinates'].shape==(450,44,3);assert motion['rotations'].shape==(450,44,4);assert np.isfinite(motion['coordinates']).all() and np.isfinite(motion['rotations']).all()
publication=dict(published_through_frame=450,run=str(out));(out/'publication.json').write_text(json.dumps(publication),'utf8');s['FullHairCachePublication']=str(out/'publication.json')
s['UserHairContactLimitCM']=5.;s['UserContactBelowLimitRecordOnly']=True;s['ReviewAllHairCollisionSolved']=False;s['ShutdownForbidden']=True
s.frame_start=151;s.frame_end=450;s.frame_set(226);s.render.fps=30;s.render.resolution_x=1920;s.render.resolution_y=1080;s.render.resolution_percentage=100
blend=out/'完整角色_原生侧发_5cm规则_5至15秒图集.blend';bpy.ops.wm.save_as_mainfile(filepath=str(blend))
report=dict(status='COMPLETE_NATIVE_BONE_BAKE_AND_CACHES_PACKAGED',blend=str(blend),source_blend=r['blend'],hair_physics_cache=str(out/'native_rod_physics.npz'),external_pc2=cache,full_character_vertices=68272,shape_keys=232,source_physics_frames=[1,450],review_frames=[151,450],user_limit_cm=5,zero_penetration_claim=False,shutdown_forbidden=True)
(out/'package_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False),flush=True)
