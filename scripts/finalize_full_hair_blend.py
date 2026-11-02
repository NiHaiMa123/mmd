"""Freeze complete replay metadata and pack image/audio resources in the new file."""
import argparse,json,sys,struct,hashlib
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'addon'))
from mmd_outfit.service import engine
p=argparse.ArgumentParser();p.add_argument('--delivery',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.delivery);pub=json.loads((out/'cache_publication.json').read_text('utf8'));assert pub['status']=='COMPLETE_PHYSICAL_TRAJECTORY';engine('import_export').ensure_mmd_tools();blend=out/'完整角色_整头连续物理_15秒.blend';bpy.ops.wm.open_mainfile(filepath=str(blend),load_ui=False,use_scripts=False);s=bpy.context.scene;assert s.frame_start==1 and s.frame_end==450 and s.render.fps==30;assert (s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage)==(1920,1080,100);assert not s.camera.animation_data and not s.camera.constraints
cache_rows=[]
for obj in s.objects:
 for mod in obj.modifiers:
  if mod.type=='MESH_CACHE':
   path=Path(bpy.path.abspath(mod.filepath));assert path.exists(),str(path);assert mod.filepath.replace('\\','/').startswith('//cache/'),(obj.name,mod.filepath);cache_rows.append(dict(object=obj.name,path=mod.filepath,bytes=path.stat().st_size))
with (out/'cache/full_head.pc2').open('rb') as f:header=struct.unpack('<12siiffi',f.read(32))
assert header[0]==b'POINTCACHE2\0' and header[2]==24207 and header[4]==.125 and header[5]==3593
s['FullHairAlgorithmFingerprint']=pub['fingerprint'];s['FullHairTrajectoryStatus']='COMPLETE 1-450 / 3593 samples';s['FullHairContactModel']=pub.get('backend','Inertial implicit elasticity + body contact + automatic harmonic geometric contact projection; not full card self-collision or CCD');s['FullHairProtectedBodyWindow']='256-321 unchanged';s.frame_set(1);bpy.context.view_layer.update();motion_blur=getattr(s.render,'use_motion_blur',None);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True,relative_remap=False)
images=[dict(name=im.name,source=im.source,packed=bool(im.packed_file or len(im.packed_files)),filepath=im.filepath) for im in bpy.data.images if im.source not in ['GENERATED','VIEWER']];meshes=[dict(name=obj.name,vertices=len(obj.data.vertices),hidden_render=obj.hide_render,ray_camera=getattr(obj,'visible_camera',None)) for obj in s.objects if obj.type=='MESH' and ('雪莲' in obj.name or 'Hair' in obj.name or 'Shadow' in obj.name or '影' in obj.name)];report=dict(status='COMPLETE_NEW_BLEND_AND_RELATIVE_CACHE_PATHS_VERIFIED',blend=str(blend),bytes=blend.stat().st_size,cache_files=cache_rows,pc2=dict(vertices=header[2],step=header[4],samples=header[5]),algorithm_fingerprint=pub['fingerprint'],motion_blur=motion_blur,images=images,character_related_meshes=meshes,fixed_camera=True);(out/'blend_delivery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('FULL_HAIR_BLEND_FINALIZED',report['bytes'],'MOTION_BLUR',motion_blur,flush=True)
